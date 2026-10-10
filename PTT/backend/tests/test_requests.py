import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.v1.endpoints.requests import approve_request, create_request, reject_request, router, send_request
from app.db.base import Base
from app.models.audit_log import AuditLog
from app.models.item import Category
from app.models.role import Role
from app.models.user import User
from app.models.warehouse_request import WarehouseRequest, WarehouseRequestItem, WarehouseRequestStatus
from app.schemas.warehouse_request import (
    WarehouseRequestCreate,
    WarehouseRequestItemIn,
    WarehouseRequestRead,
    WarehouseRequestReject,
)


class WarehouseRequestTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine, tables=[
            Role.__table__, User.__table__, Category.__table__, WarehouseRequest.__table__,
            WarehouseRequestItem.__table__, AuditLog.__table__,
        ])

        def set_test_timestamps(mapper, connection, target):
            now = datetime.now(timezone.utc)
            if isinstance(target, User):
                target.created_at = now
                target.updated_at = now
            elif isinstance(target, WarehouseRequest):
                target.created_at = now
            elif isinstance(target, AuditLog):
                target.timestamp = now

        self.set_test_timestamps = set_test_timestamps
        for model in (User, WarehouseRequest, AuditLog):
            event.listen(model, "before_insert", set_test_timestamps)
        self.db = Session(self.engine)
        self.db.add_all([
            Role(id=1, name="administrador"), Role(id=2, name="encargado_inventario"),
            User(id=1, username="admin", email="admin@example.com", full_name="Admin", hashed_password="unused",
                 role_id=1, is_active=True, created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc)),
            User(id=2, username="keeper", email="keeper@example.com", full_name="Encargado", hashed_password="unused",
                 role_id=2, is_active=True, created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc)),
            Category(id=1, name="Seguridad"),
        ])
        self.db.commit()
        self.admin = self.db.get(User, 1)
        self.keeper = self.db.get(User, 2)

    def tearDown(self):
        self.db.close()
        for model in (User, WarehouseRequest, AuditLog):
            event.remove(model, "before_insert", self.set_test_timestamps)
        self.engine.dispose()

    def test_create_list_approve_and_reject_are_audited_and_relational(self):
        payload = WarehouseRequestCreate(items=[
            WarehouseRequestItemIn(category_id=1, description="Guantes", quantity=5),
            WarehouseRequestItemIn(category_id=None, description="Cinta aislante", quantity=3),
        ])
        created = create_request(payload, db=self.db, current_user=self.keeper)
        response = WarehouseRequestRead.model_validate(created)
        self.assertEqual(response.requester_name, "Encargado")
        self.assertEqual(response.items[0].category_name, "Seguridad")
        self.assertIsNone(response.items[1].category_name)
        self.assertNotIn("category_name", WarehouseRequestItem.__table__.columns.keys())
        self.assertEqual(self.db.query(AuditLog).filter(
            AuditLog.action == "warehouse_request.create", AuditLog.entity_id == created.id
        ).one().user_id, self.keeper.id)

        approved = approve_request(created.id, db=self.db, current_user=self.admin)
        self.assertEqual(approved.status, WarehouseRequestStatus.APROBADA)
        self.assertEqual(approved.approved_by_user_id, self.admin.id)
        with self.assertRaises(HTTPException) as duplicate_approval:
            approve_request(created.id, db=self.db, current_user=self.admin)
        self.assertEqual(duplicate_approval.exception.status_code, 409)
        sent = send_request(created.id, db=self.db, current_user=self.admin)
        self.assertEqual(sent.status, WarehouseRequestStatus.ENVIADA)
        with self.assertRaises(HTTPException) as duplicate_send:
            send_request(created.id, db=self.db, current_user=self.admin)
        self.assertEqual(duplicate_send.exception.status_code, 409)

        rejected_request = create_request(
            WarehouseRequestCreate(items=[WarehouseRequestItemIn(description="Casco", quantity=1)]),
            db=self.db,
            current_user=self.keeper,
        )
        rejected = reject_request(
            rejected_request.id,
            WarehouseRequestReject(reason="Fuera de presupuesto"),
            db=self.db,
            current_user=self.admin,
        )
        self.assertEqual(rejected.status, WarehouseRequestStatus.RECHAZADA)
        self.assertEqual(rejected.rejection_reason, "Fuera de presupuesto")
        self.assertEqual(rejected.rejecter_name, "Admin")
        actions = {row.action for row in self.db.query(AuditLog).filter(
            AuditLog.entity_type == "warehouse_request"
        ).all()}
        self.assertTrue({"warehouse_request.create", "warehouse_request.approve", "warehouse_request.send", "warehouse_request.reject"} <= actions)

    def test_invalid_category_and_empty_or_invalid_lines_are_rejected(self):
        with self.assertRaises(HTTPException) as invalid_category:
            create_request(
                WarehouseRequestCreate(items=[WarehouseRequestItemIn(category_id=999, description="Item", quantity=1)]),
                db=self.db,
                current_user=self.keeper,
            )
        self.assertEqual(invalid_category.exception.status_code, 400)
        with self.assertRaises(ValidationError):
            WarehouseRequestCreate(items=[])
        with self.assertRaises(ValidationError):
            WarehouseRequestItemIn(description=" ", quantity=1)
        with self.assertRaises(ValidationError):
            WarehouseRequestItemIn(description="Item", quantity=0)

    def test_reject_and_send_routes_are_admin_only_and_authenticated(self):

        def depends_on_user(dependant):
            return any(
                dependency.call is get_current_user or depends_on_user(dependency)
                for dependency in dependant.dependencies
            )

        def find_admin_guard(dependant):
            for dependency in dependant.dependencies:
                if dependency.call.__name__ == "_checker":
                    return dependency.call
                nested = find_admin_guard(dependency)
                if nested:
                    return nested
            return None

        for path in ("/{request_id}/reject", "/{request_id}/send"):
            route = next(route for route in router.routes if route.path == path)
            self.assertTrue(depends_on_user(route.dependant))
            guard = find_admin_guard(route.dependant)
            self.assertIsNotNone(guard)
            with self.assertRaises(HTTPException) as denied:
                guard(SimpleNamespace(role=SimpleNamespace(name="jefe_area")))
            self.assertEqual(denied.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()