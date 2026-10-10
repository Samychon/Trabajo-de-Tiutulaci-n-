import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.v1.endpoints.users import create_user, deactivate_user, reactivate_user, router, update_user
import app.db.base  # noqa: F401
from app.core.security import hash_password, verify_password
from app.db.session import Base
from app.models.audit_log import AuditLog
from app.models.role import Role
from app.models.user import User
from app.models.user_preferences import UserPreferences
from app.schemas.preferences import UserPreferencesUpdate
from app.schemas.user import RoleRead, UserCreate, UserDeactivateRequest, UserRead, UserReactivateRequest, UserUpdate
from app.api.v1.endpoints.users import read_my_preferences, update_my_preferences


class UserAdministrationTests(unittest.TestCase):
    def test_user_preferences_are_self_scoped_and_validated(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine, tables=[Role.__table__, User.__table__, UserPreferences.__table__])
        now = datetime.now(timezone.utc)
        try:
            with Session(engine) as db:
                db.add_all([
                    Role(id=1, name="administrador"),
                    User(id=1, username="admin", email="admin@example.com", full_name="Admin",
                         hashed_password="unused", role_id=1, is_active=True, created_at=now, updated_at=now),
                    User(id=2, username="user", email="user@example.com", full_name="User",
                         hashed_password="unused", role_id=1, is_active=True, created_at=now, updated_at=now),
                ])
                db.commit()
                first_user = db.get(User, 1)
                second_user = db.get(User, 2)

                defaults = read_my_preferences(db=db, current_user=first_user)
                self.assertEqual(defaults.report_default_period, "week")
                self.assertEqual(defaults.alert_status_filter, "all")

                saved = update_my_preferences(
                    UserPreferencesUpdate(
                        report_default_period="month",
                        alert_status_filter="resuelta",
                        alert_type_filter="falla_dispositivo",
                    ),
                    db=db,
                    current_user=first_user,
                )
                self.assertEqual(saved.report_default_period, "month")
                other_user_preferences = read_my_preferences(db=db, current_user=second_user)
                self.assertEqual(other_user_preferences.report_default_period, "week")
                self.assertEqual(db.query(UserPreferences).count(), 1)

                with self.assertRaises(ValidationError):
                    UserPreferencesUpdate(
                        report_default_period="year",
                        alert_status_filter="all",
                        alert_type_filter="all",
                    )
                with self.assertRaises(ValidationError):
                    UserPreferencesUpdate(
                        report_default_period="week",
                        alert_status_filter="all",
                        alert_type_filter="all",
                        role="administrador",
                    )
        finally:
            engine.dispose()

    def test_user_contract_requires_strong_password_and_bounded_fields(self):
        with self.assertRaises(ValidationError):
            UserCreate(username="new", email="new@example.com", full_name="New User", password="short", role_id=1)
        with self.assertRaises(ValidationError):
            UserCreate(username="ab", email="new@example.com", full_name="New User", password="LongPassword123!", role_id=1)
        payload = UserCreate(
            username="new.user", email="new@example.com", full_name="New User",
            password="LongPassword123!", role_id=2,
        )
        self.assertEqual(payload.username, "new.user")

    def test_create_user_returns_role_without_password_and_audits_creator(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine, tables=[Role.__table__, User.__table__, AuditLog.__table__])

        def set_test_timestamps(mapper, connection, target):
            now = datetime.now(timezone.utc)
            if isinstance(target, User):
                target.created_at = now
                target.updated_at = now
            elif isinstance(target, AuditLog):
                target.timestamp = now

        event.listen(User, "before_insert", set_test_timestamps)
        event.listen(AuditLog, "before_insert", set_test_timestamps)
        try:
            with Session(engine) as db:
                db.add_all([Role(id=1, name="administrador"), Role(id=2, name="jefe_area")])
                admin = User(
                    id=1, username="admin", email="admin@example.com", full_name="Admin", hashed_password="unused",
                    role_id=1, is_active=True, created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
                )
                db.add(admin)
                db.commit()
                created = create_user(
                    UserCreate(
                        username="chief", email="chief@example.com", full_name="Jefe Area",
                        password="LongPassword123!", role_id=2,
                    ),
                    db=db,
                    current_user=admin,
                )
                response = UserRead.model_validate(created)
                self.assertEqual(response.role_name, "jefe_area")
                self.assertNotIn("hashed_password", response.model_dump())
                self.assertNotIn("password", response.model_dump())
                self.assertEqual(db.query(AuditLog).filter(
                    AuditLog.action == "user.create", AuditLog.entity_id == created.id
                ).one().user_id, admin.id)
                self.assertEqual(RoleRead.model_validate({"id": 2, "name": "jefe_area", "description": None}).name, "jefe_area")

                with self.assertRaises(HTTPException) as duplicate:
                    create_user(
                        UserCreate(
                            username="chief", email="other@example.com", full_name="Another",
                            password="LongPassword123!", role_id=2,
                        ),
                        db=db,
                        current_user=admin,
                    )
                self.assertEqual(duplicate.exception.status_code, 409)
                with self.assertRaises(HTTPException) as invalid_role:
                    create_user(
                        UserCreate(
                            username="other", email="other@example.com", full_name="Another",
                            password="LongPassword123!", role_id=999,
                        ),
                        db=db,
                        current_user=admin,
                    )
                self.assertEqual(invalid_role.exception.status_code, 400)
        finally:
            event.remove(User, "before_insert", set_test_timestamps)
            event.remove(AuditLog, "before_insert", set_test_timestamps)
            engine.dispose()

    def test_management_routes_require_admin_role_and_session(self):
        def find_role_guard(dependant):
            for dependency in dependant.dependencies:
                if dependency.call.__name__ == "_checker":
                    return dependency.call
                nested = find_role_guard(dependency)
                if nested:
                    return nested
            return None

        for path in ("", "/roles"):
            route = next(route for route in router.routes if route.path == path and "GET" in route.methods)
            self.assertTrue(any(
                dependency.call is get_current_user or self._depends_on_user(dependency)
                for dependency in route.dependant.dependencies
            ))
            guard = find_role_guard(route.dependant)
            self.assertIsNotNone(guard)
            with self.assertRaises(HTTPException) as denied:
                guard(SimpleNamespace(role=SimpleNamespace(name="jefe_area")))
            self.assertEqual(denied.exception.status_code, 403)

        for path, method in (("/{user_id}", "PATCH"), ("/{user_id}/deactivate", "POST"), ("/{user_id}/reactivate", "POST")):
            route = next(route for route in router.routes if route.path == path and method in route.methods)
            self.assertTrue(self._depends_on_user(route.dependant))
            guard = find_role_guard(route.dependant)
            self.assertIsNotNone(guard)
            with self.assertRaises(HTTPException) as denied:
                guard(SimpleNamespace(role=SimpleNamespace(name="jefe_area")))
            self.assertEqual(denied.exception.status_code, 403)

    def test_update_and_soft_deactivate_user_preserve_row_and_audit(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine, tables=[Role.__table__, User.__table__, AuditLog.__table__])

        def set_test_timestamps(mapper, connection, target):
            now = datetime.now(timezone.utc)
            if isinstance(target, User):
                target.created_at = now
                target.updated_at = now
            elif isinstance(target, AuditLog):
                target.timestamp = now

        event.listen(User, "before_insert", set_test_timestamps)
        event.listen(AuditLog, "before_insert", set_test_timestamps)
        try:
            with Session(engine) as db:
                db.add_all([Role(id=1, name="administrador"), Role(id=2, name="jefe_area")])
                admin = User(
                    id=1, username="admin", email="admin@example.com", full_name="Admin",
                    hashed_password=hash_password("AdminStrongPassword123!"), role_id=1, is_active=True,
                    created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
                )
                target = User(
                    id=2, username="chief", email="chief@example.com", full_name="Jefe Inicial",
                    hashed_password=hash_password("OldStrongPassword123!"), role_id=2, is_active=True,
                    created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
                )
                db.add_all([admin, target]);db.commit()

                updated = update_user(
                    2,
                    UserUpdate(username="chief.new", full_name="Jefe Nuevo", password="NewStrongPassword123!"),
                    db=db,
                    current_user=admin,
                )
                self.assertEqual(updated.username, "chief.new")
                self.assertEqual(updated.full_name, "Jefe Nuevo")
                self.assertTrue(verify_password("NewStrongPassword123!", updated.hashed_password))
                self.assertNotIn("hashed_password", UserRead.model_validate(updated).model_dump())
                self.assertEqual(db.query(AuditLog).filter(
                    AuditLog.action == "user.update", AuditLog.entity_id == updated.id
                ).count(), 1)
                update_log = db.query(AuditLog).filter(AuditLog.action == "user.update").one()
                self.assertNotIn("password", update_log.details)

                with self.assertRaises(HTTPException) as self_username:
                    update_user(1, UserUpdate(username="admin.new"), db=db, current_user=admin)
                self.assertEqual(self_username.exception.status_code, 409)
                with self.assertRaises(HTTPException) as self_role:
                    update_user(1, UserUpdate(role_id=2), db=db, current_user=admin)
                self.assertEqual(self_role.exception.status_code, 409)

                with self.assertRaises(HTTPException) as duplicate:
                    update_user(2, UserUpdate(email="admin@example.com"), db=db, current_user=admin)
                self.assertEqual(duplicate.exception.status_code, 409)

                with self.assertRaises(HTTPException) as wrong_password:
                    deactivate_user(
                        2, UserDeactivateRequest(confirmation_password="wrong-password"), db=db, current_user=admin
                    )
                self.assertEqual(wrong_password.exception.status_code, 403)
                self.assertTrue(db.get(User, 2).is_active)

                deactivated = deactivate_user(
                    2, UserDeactivateRequest(confirmation_password="AdminStrongPassword123!"), db=db, current_user=admin
                )
                self.assertFalse(deactivated.is_active)
                self.assertIsNotNone(db.get(User, 2))
                self.assertEqual(db.query(AuditLog).filter(
                    AuditLog.action == "user.deactivate", AuditLog.entity_id == 2
                ).one().user_id, admin.id)

                with self.assertRaises(HTTPException) as invalid_reactivation_password:
                    reactivate_user(
                        2, UserReactivateRequest(confirmation_password="wrong-password"), db=db, current_user=admin
                    )
                self.assertEqual(invalid_reactivation_password.exception.status_code, 403)
                self.assertFalse(db.get(User, 2).is_active)

                reactivated = reactivate_user(
                    2, UserReactivateRequest(confirmation_password="AdminStrongPassword123!"),
                    db=db, current_user=admin,
                )
                self.assertTrue(reactivated.is_active)
                self.assertEqual(db.query(AuditLog).filter(
                    AuditLog.action == "user.reactivate", AuditLog.entity_id == 2
                ).one().user_id, admin.id)
                with self.assertRaises(HTTPException) as duplicate_reactivation:
                    reactivate_user(
                        2, UserReactivateRequest(confirmation_password="AdminStrongPassword123!"),
                        db=db, current_user=admin,
                    )
                self.assertEqual(duplicate_reactivation.exception.status_code, 409)

                with self.assertRaises(HTTPException) as self_deactivation:
                    deactivate_user(
                        1, UserDeactivateRequest(confirmation_password="AdminStrongPassword123!"),
                        db=db, current_user=admin,
                    )
                self.assertEqual(self_deactivation.exception.status_code, 409)
                self.assertTrue(db.get(User, 1).is_active)
        finally:
            event.remove(User, "before_insert", set_test_timestamps)
            event.remove(AuditLog, "before_insert", set_test_timestamps)
            engine.dispose()

    @staticmethod
    def _depends_on_user(dependant):
        return any(
            dependency.call is get_current_user or UserAdministrationTests._depends_on_user(dependency)
            for dependency in dependant.dependencies
        )


if __name__ == "__main__":
    unittest.main()