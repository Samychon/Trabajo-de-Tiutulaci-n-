import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.v1.endpoints.items import decommission_item, router
from app.db.session import Base
from app.models.audit_log import AuditLog
from app.models.decommission import ItemDecommission
from app.models.item import Category, Item, ItemStatus, ItemType
from app.models.location import Location
from app.models.movement import Movement, MovementStatus
from app.models.role import Role
from app.models.user import User
from app.schemas.decommission import ItemDecommissionCreate, ItemDecommissionRead


class ItemDecommissionTests(unittest.TestCase):
    def make_database(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine, tables=[
            Role.__table__, User.__table__, Category.__table__, Location.__table__, Item.__table__,
            Movement.__table__, ItemDecommission.__table__, AuditLog.__table__,
        ])

        def set_test_dates(mapper, connection, target):
            now = datetime.now(timezone.utc)
            if isinstance(target, Item):
                target.created_at = now
                target.updated_at = now
            elif isinstance(target, Movement):
                target.created_at = now
            elif isinstance(target, ItemDecommission):
                target.decommissioned_at = now
            elif isinstance(target, AuditLog):
                target.timestamp = now

        for model in (Item, Movement, ItemDecommission, AuditLog):
            event.listen(model, "before_insert", set_test_dates)
        return engine, set_test_dates

    @staticmethod
    def seed_item(db, status=ItemStatus.DISPONIBLE):
        db.add(Role(id=1, name="administrador"))
        db.add(User(
            id=1, username="admin", email="admin@example.com", full_name="Admin", hashed_password="unused",
            role_id=1, is_active=True, created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
        ))
        db.add(Location(id=1, name="Almacen"))
        db.add(Category(id=1, name="Taladro"))
        db.add(Item(
            id=1, code="TAL-ABC123", name="Taladro", type=ItemType.HERRAMIENTA,
            category_id=1, location_id=1, status=status,
        ))
        db.commit()

    def test_decommission_is_atomic_audited_and_relational(self):
        engine, set_test_dates = self.make_database()
        try:
            with Session(engine) as db:
                self.seed_item(db)
                admin = db.get(User, 1)
                payload = ItemDecommissionCreate(
                    reason="Robo", description="Reporte confirmado", notes="Folio 42", confirmation_password="valid"
                )
                with patch("app.api.v1.endpoints.items.verify_password", return_value=True):
                    result = decommission_item(1, payload, db=db, current_user=admin)
                response = ItemDecommissionRead.model_validate(result)

                self.assertEqual(db.get(Item, 1).status, ItemStatus.BAJA)
                self.assertEqual(response.item_code, "TAL-ABC123")
                self.assertEqual(response.item_name, "Taladro")
                self.assertEqual(response.administrator_name, "Admin")
                self.assertEqual(db.query(AuditLog).filter(
                    AuditLog.action == "item.decommission", AuditLog.entity_id == result.id
                ).count(), 1)
                self.assertNotIn("item_code", ItemDecommission.__table__.columns.keys())
                self.assertNotIn("item_name", ItemDecommission.__table__.columns.keys())

                with patch("app.api.v1.endpoints.items.verify_password", return_value=True):
                    with self.assertRaises(HTTPException) as duplicate:
                        decommission_item(1, payload, db=db, current_user=admin)
                self.assertEqual(duplicate.exception.status_code, 409)
                self.assertEqual(db.query(ItemDecommission).count(), 1)
        finally:
            for model in (Item, Movement, ItemDecommission, AuditLog):
                event.remove(model, "before_insert", set_test_dates)
            engine.dispose()

    def test_open_or_pending_movement_blocks_decommission(self):
        engine, set_test_dates = self.make_database()
        try:
            with Session(engine) as db:
                self.seed_item(db)
                db.add(Movement(
                    id=1, item_id=1, responsible_user_id=1, location_id=1,
                    purpose="Salida pendiente", status=MovementStatus.PENDING_AUTHORIZATION,
                ))
                db.commit()

                with patch("app.api.v1.endpoints.items.verify_password", return_value=True):
                    with self.assertRaises(HTTPException) as blocked:
                        decommission_item(
                            1,
                            ItemDecommissionCreate(
                                reason="Dano", description="No debe procesarse", confirmation_password="valid"
                            ),
                            db=db,
                            current_user=db.get(User, 1),
                        )
                self.assertEqual(blocked.exception.status_code, 409)
                self.assertEqual(db.get(Item, 1).status, ItemStatus.DISPONIBLE)
                self.assertEqual(db.query(ItemDecommission).count(), 0)
        finally:
            for model in (Item, Movement, ItemDecommission, AuditLog):
                event.remove(model, "before_insert", set_test_dates)
            engine.dispose()

    def test_decommission_route_is_admin_only_and_payload_is_bounded(self):
        route = next(route for route in router.routes if route.path == "/{item_id}/decommission")

        def find_role_guard(dependant):
            for dependency in dependant.dependencies:
                if dependency.call.__name__ == "_checker":
                    return dependency.call
                nested = find_role_guard(dependency)
                if nested:
                    return nested
            return None

        role_guard = find_role_guard(route.dependant)
        self.assertIsNotNone(role_guard)
        with self.assertRaises(HTTPException) as denied:
            role_guard(SimpleNamespace(role=SimpleNamespace(name="encargado_inventario")))
        self.assertEqual(denied.exception.status_code, 403)
        with patch("app.api.v1.endpoints.items.verify_password", return_value=False):
            with self.assertRaises(HTTPException) as bad_password:
                decommission_item(
                    1,
                    ItemDecommissionCreate(reason="Robo", description="Reporte", confirmation_password="bad"),
                    db=MagicMock(),
                    current_user=SimpleNamespace(id=1, hashed_password="hashed"),
                )
        self.assertEqual(bad_password.exception.status_code, 403)
        for role in ("administrador",):
            self.assertIsNotNone(role_guard(SimpleNamespace(role=SimpleNamespace(name=role))))
        with self.assertRaises(ValidationError):
            ItemDecommissionCreate(reason="x" * 101, description="Descripcion", confirmation_password="valid")
        with self.assertRaises(ValidationError):
            ItemDecommissionCreate(reason="Otro", description=" ", confirmation_password="valid")


if __name__ == "__main__":
    unittest.main()