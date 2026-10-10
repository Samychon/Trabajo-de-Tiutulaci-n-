import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.v1.endpoints.movements import authorize_movement, create_movement, return_movement, router
from app.db.session import Base
from app.models.audit_log import AuditLog
from app.models.item import Category, Item, ItemStatus, ItemType
from app.models.location import Location
from app.models.movement import Movement, MovementStatus
from app.models.role import Role
from app.models.user import User
from app.schemas.auth import MovementAuthorizationRequest
from app.schemas.movement import MovementCreate, MovementRead


class MovementHistoryTests(unittest.TestCase):
    def test_history_response_includes_related_labels(self):
        movement = SimpleNamespace(
            id=42,
            item_id=2,
            responsible_user_id=3,
            authorized_by_user_id=4,
            location_id=5,
            purpose="Mantenimiento",
            auth_method="password",
            status=MovementStatus.OPEN,
            checkout_at=datetime(2026, 9, 29, tzinfo=timezone.utc),
            checkin_at=None,
            item_code="HER-ABC123",
            item_name="Llave combinada",
            responsible_name="Usuario responsable",
            authorizer_name="Jefe de area",
            location_name="Taller",
        )

        response = MovementRead.model_validate(movement)

        self.assertEqual(response.item_code, "HER-ABC123")
        self.assertEqual(response.responsible_name, "Usuario responsable")
        self.assertEqual(response.authorizer_name, "Jefe de area")
        self.assertEqual(response.location_name, "Taller")

    def test_history_route_requires_authenticated_user(self):
        def requires_user(dependant):
            return any(
                dependency.call is get_current_user or requires_user(dependency)
                for dependency in dependant.dependencies
            )

        for path in ("", "/options"):
            route = next(route for route in router.routes if route.path == path)
            self.assertTrue(requires_user(route.dependant), path)

    def test_create_movement_rejects_second_open_request(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine, tables=[
            Role.__table__, User.__table__, Category.__table__, Location.__table__, Item.__table__,
            Movement.__table__, AuditLog.__table__,
        ])

        def set_test_dates(mapper, connection, target):
            now = datetime.now(timezone.utc)
            if isinstance(target, (Item, Movement)):
                target.created_at = now
            if isinstance(target, Item):
                target.updated_at = now
            if isinstance(target, AuditLog):
                target.timestamp = now

        for model in (Item, Movement, AuditLog):
            event.listen(model, "before_insert", set_test_dates)
        try:
            with Session(engine) as db:
                db.add(Role(id=1, name="encargado_inventario"))
                db.add(User(
                    id=1, username="keeper", email="keeper@example.com", full_name="Encargado",
                    hashed_password="unused", role_id=1, is_active=True,
                    created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
                ))
                db.add(Location(id=1, name="Taller"))
                db.add(Category(id=1, name="Taladro"))
                db.add(Item(
                    id=1, code="TAL-ABC123", name="Taladro", type=ItemType.HERRAMIENTA,
                    category_id=1, status=ItemStatus.DEVUELTA,
                ))
                db.commit()
                keeper = db.get(User, 1)
                payload = MovementCreate(item_id=1, responsible_user_id=1, location_id=1, purpose="Mantenimiento")
                first = create_movement(payload, db=db, current_user=keeper)
                result = MovementRead.model_validate(first)
                self.assertEqual(result.status, MovementStatus.PENDING_AUTHORIZATION)
                self.assertEqual(result.item_code, "TAL-ABC123")
                with self.assertRaises(HTTPException) as duplicate:
                    create_movement(payload, db=db, current_user=keeper)
                self.assertEqual(duplicate.exception.status_code, 409)
                self.assertEqual(db.query(Movement).count(), 1)
        finally:
            for model in (Item, Movement, AuditLog):
                event.remove(model, "before_insert", set_test_dates)
            engine.dispose()

    def test_authorize_locks_rows_and_rejects_repeated_authorization(self):
        movement = SimpleNamespace(
            id=12, item_id=7, status=MovementStatus.PENDING_AUTHORIZATION,
            authorized_by_user_id=None, auth_method=None, checkout_at=None,
        )
        item = SimpleNamespace(status=ItemStatus.DISPONIBLE)
        authorizer = SimpleNamespace(
            id=9, is_active=True, hashed_password="unused", role=SimpleNamespace(name="jefe_area"),
        )
        db = MagicMock()
        locked = db.query.return_value.filter.return_value.with_for_update.return_value
        locked.first.side_effect = [movement, item, movement]
        db.query.return_value.filter.return_value.first.return_value = authorizer
        payload = MovementAuthorizationRequest(method="password", username="jefe", password="secret")

        with patch("app.api.v1.endpoints.movements.verify_password", return_value=True), \
                patch("app.api.v1.endpoints.movements.record_audit") as record_audit:
            result = authorize_movement(12, payload, db=db)
            self.assertEqual(result.status, MovementStatus.OPEN)
            self.assertEqual(item.status, ItemStatus.EN_USO)
            self.assertEqual(locked.first.call_count, 2)

            with self.assertRaises(HTTPException) as repeated:
                authorize_movement(12, payload, db=db)
            self.assertEqual(repeated.exception.status_code, 400)
            record_audit.assert_called_once()
            db.commit.assert_called_once()

    def test_return_closes_movement_restores_item_and_rejects_repeat(self):
        movement = SimpleNamespace(id=12, item_id=7, status=MovementStatus.OPEN, checkin_at=None)
        item = SimpleNamespace(status=ItemStatus.EN_USO)
        db = MagicMock()
        db.query.return_value.filter.return_value.with_for_update.return_value.first.side_effect = [movement, item, movement]
        current_user = SimpleNamespace(id=4)

        with patch("app.api.v1.endpoints.movements.record_audit") as record_audit:
            result = return_movement(12, db=db, current_user=current_user)

            self.assertEqual(result.status, MovementStatus.CLOSED)
            self.assertEqual(item.status, ItemStatus.DEVUELTA)
            self.assertIsNotNone(result.checkin_at)
            record_audit.assert_called_once_with(
                db, user_id=4, action="movement.return", entity_type="movement", entity_id=12, commit=False
            )
            db.commit.assert_called_once()

            with self.assertRaises(HTTPException) as repeated:
                return_movement(12, db=db, current_user=current_user)
            self.assertEqual(repeated.exception.status_code, 409)

    def test_return_route_restricts_role_and_state_mismatch(self):
        route = next(route for route in router.routes if route.path == "/{movement_id}/return")
        role_guard = next(dependency.call for dependency in route.dependant.dependencies if dependency.call.__name__ == "_checker")
        with self.assertRaises(HTTPException) as denied:
            role_guard(SimpleNamespace(role=SimpleNamespace(name="jefe_area")))
        self.assertEqual(denied.exception.status_code, 403)

        movement = SimpleNamespace(id=12, item_id=7, status=MovementStatus.PENDING_AUTHORIZATION, checkin_at=None)
        db = MagicMock()
        db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = movement
        with self.assertRaises(HTTPException) as invalid_state:
            return_movement(12, db=db, current_user=SimpleNamespace(id=4))
        self.assertEqual(invalid_state.exception.status_code, 409)
        db.commit.assert_not_called()


if __name__ == "__main__":
    unittest.main()