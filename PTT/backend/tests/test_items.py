import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.api.v1.endpoints.items import _get_or_create_by_name, create_item
from app.db.session import Base
from app.models.audit_log import AuditLog
from app.models.item import Category, Item
from app.models.location import Location
from app.models.role import Role
from app.models.user import User
from app.schemas.item import ItemCreate, ItemRead


class ItemCreationTests(unittest.TestCase):
    def test_get_or_create_reuses_row_created_by_a_concurrent_request(self):
        existing = SimpleNamespace(id=5, name="Prueba")
        db = MagicMock()
        query = db.query.return_value.filter.return_value
        query.first.return_value = None
        query.one.return_value = existing
        db.begin_nested.return_value.__exit__.return_value = False
        db.add.side_effect = IntegrityError("insert", {}, Exception("duplicate"))

        self.assertIs(_get_or_create_by_name(db, Category, "Prueba"), existing)

    def test_get_or_create_returns_existing_row_without_inserting(self):
        existing = SimpleNamespace(id=7, name="Bodega")
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = existing

        self.assertIs(_get_or_create_by_name(db, Location, "Bodega"), existing)
        db.add.assert_not_called()

    def test_item_audit_is_written_in_the_same_transaction(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        db.begin_nested.return_value.__exit__.return_value = False
        admin = SimpleNamespace(id=1)
        payload = ItemCreate(name="Taladro", type="herramienta", code="TAL-1")

        with patch("app.api.v1.endpoints.items.record_audit") as record_audit:
            create_item(payload, db=db, current_user=admin)

        self.assertFalse(record_audit.call_args.kwargs.get("commit", True))
        db.commit.assert_called_once()

    def test_contract_rejects_invalid_details(self):
        for payload in (
            {"name": "  ", "type": "herramienta"},
            {"name": "Motor", "type": "inexistente"},
            {"name": "Motor", "type": "herramienta", "location_name": " "},
            {"name": "Motor", "type": "herramienta", "specs": {"modelo": "x" * 151}},
        ):
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                ItemCreate.model_validate(payload)

    def test_only_operational_roles_can_create_items(self):
        dependency = require_roles("administrador", "encargado_inventario")
        with self.assertRaises(HTTPException) as denied:
            dependency(SimpleNamespace(role=SimpleNamespace(name="jefe_area")))
        self.assertEqual(denied.exception.status_code, 403)
        for role in ("administrador", "encargado_inventario"):
            self.assertIsNotNone(dependency(SimpleNamespace(role=SimpleNamespace(name=role))))

    def test_create_item_persists_details_and_audit_without_duplicate(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(
            engine, tables=[Role.__table__, User.__table__, Category.__table__, Location.__table__, Item.__table__, AuditLog.__table__]
        )

        def set_test_dates(mapper, connection, target):
            now = datetime.now(timezone.utc)
            if isinstance(target, Item):
                target.created_at = now
                target.updated_at = now
            elif isinstance(target, AuditLog):
                target.timestamp = now

        event.listen(Item, "before_insert", set_test_dates)
        event.listen(AuditLog, "before_insert", set_test_dates)
        try:
            with Session(engine) as db:
                db.add(Role(id=1, name="administrador"))
                db.add(User(
                    id=1, username="admin", email="admin@example.com", full_name="Admin", hashed_password="unused",
                    role_id=1, is_active=True, created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
                ))
                db.commit()
                admin = db.get(User, 1)
                payload = ItemCreate(
                    name="Bomba", type="herramienta", category_name="Bomba", location_name="Almacen",
                    description="Mover agua", specs={"modelo": "Horizontal"},
                )
                created = create_item(payload, db=db, current_user=admin)
                result = ItemRead.model_validate(created)
                self.assertTrue(result.code.startswith("BOM-"))
                self.assertEqual(result.category_name, "Bomba")
                self.assertEqual(result.location_name, "Almacen")
                self.assertEqual(result.specs.modelo, "Horizontal")
                self.assertEqual(db.query(AuditLog).filter(AuditLog.entity_id == created.id).count(), 1)

                with self.assertRaises(HTTPException) as duplicate:
                    create_item(ItemCreate(name="Otro", type="herramienta", code=result.code), db=db, current_user=admin)
                self.assertEqual(duplicate.exception.status_code, 409)
                self.assertEqual(db.query(Item).count(), 1)
        finally:
            event.remove(Item, "before_insert", set_test_dates)
            event.remove(AuditLog, "before_insert", set_test_dates)
            engine.dispose()


if __name__ == "__main__":
    unittest.main()