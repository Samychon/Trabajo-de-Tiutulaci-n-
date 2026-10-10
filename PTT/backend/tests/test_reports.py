import unittest
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from redis.exceptions import RedisError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.v1.endpoints.reports import (
    export_movement_history_pdf,
    export_summary_pdf,
    movement_report_window,
    report_windows,
    router,
    summarize_reports,
)
from app.db.base import Base
from app.models.alert import Alert, AlertStatus, AlertType
from app.models.audit_log import AuditLog
from app.models.item import Category, Item, ItemStatus, ItemType
from app.models.location import Location
from app.models.movement import Movement, MovementStatus
from app.models.report import Report
from app.models.role import Role
from app.models.user import User
from app.schemas.report import ReportSummary
from app.services.rate_limit_service import enforce_report_pdf_limit


class ReportTests(unittest.TestCase):
    def test_movement_report_window_is_inclusive_and_limited_to_twelve_months(self):
        start, end = movement_report_window(date(2025, 10, 4), date(2026, 10, 3))
        self.assertEqual(start, datetime(2025, 10, 4, 6, tzinfo=timezone.utc))
        self.assertEqual(end, datetime(2026, 10, 4, 6, tzinfo=timezone.utc))
        with self.assertRaises(HTTPException) as too_long:
            movement_report_window(date(2025, 10, 4), date(2026, 10, 4))
        self.assertEqual(too_long.exception.status_code, 422)
        with self.assertRaises(HTTPException) as reversed_range:
            movement_report_window(date(2026, 10, 5), date(2026, 10, 4))
        self.assertEqual(reversed_range.exception.status_code, 422)

    def test_movement_pdf_filters_activity_and_audits_without_storing_file(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine, tables=[
            Role.__table__, User.__table__, Category.__table__, Location.__table__, Item.__table__,
            Movement.__table__, Report.__table__, AuditLog.__table__,
        ])
        now = datetime(2026, 10, 31, 23, 59, tzinfo=timezone.utc)

        def set_test_timestamps(mapper, connection, target):
            if isinstance(target, User):
                target.created_at = now
                target.updated_at = now
            elif isinstance(target, Report):
                target.generated_at = now
            elif isinstance(target, AuditLog):
                target.timestamp = now

        from sqlalchemy import event
        for model in (User, Report, AuditLog):
            event.listen(model, "before_insert", set_test_timestamps)
        try:
            with Session(engine) as db:
                db.add(Role(id=1, name="administrador"))
                db.add(User(
                    id=1, username="admin", email="admin@example.com", full_name="Admin", hashed_password="unused",
                    role_id=1, is_active=True, created_at=now, updated_at=now,
                ))
                db.add(Category(id=1, name="Seguridad"))
                db.add(Location(id=1, name="Bodega"))
                db.add(Item(
                    id=1, code="MAT-1", name="Guantes", type=ItemType.MATERIAL, category_id=1,
                    status=ItemStatus.DISPONIBLE, created_at=now, updated_at=now,
                ))
                db.add(Item(
                    id=2, code="MAT-2", name="Casco", type=ItemType.MATERIAL, category_id=1,
                    status=ItemStatus.DISPONIBLE, created_at=now, updated_at=now,
                ))
                db.flush()
                db.add_all([
                    Movement(
                        id=1, item_id=1, responsible_user_id=1, location_id=1, purpose="Revision mensual",
                        status=MovementStatus.CLOSED, checkout_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
                        checkin_at=now, created_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
                    ),
                    Movement(
                        id=2, item_id=2, responsible_user_id=1, location_id=1, purpose="Fuera del periodo",
                        status=MovementStatus.OPEN, checkout_at=datetime(2026, 9, 30, tzinfo=timezone.utc),
                        checkin_at=None, created_at=datetime(2026, 9, 30, tzinfo=timezone.utc),
                    ),
                ])
                db.commit()
                with patch("app.api.v1.endpoints.reports.enforce_report_pdf_limit"):
                    response = export_movement_history_pdf(
                        date(2026, 10, 1), date(2026, 10, 31),
                        movement_status=MovementStatus.CLOSED, item_id=None, category_id=1,
                        location_id=None, responsible_user_id=None,
                        db=db, current_user=db.get(User, 1),
                    )

                report = db.query(Report).one()
                audit = db.query(AuditLog).filter(AuditLog.action == "report.export_movement_pdf").one()
                self.assertEqual(response.media_type, "application/pdf")
                self.assertTrue(response.body.startswith(b"%PDF-"))
                self.assertEqual(response.headers["cache-control"], "private, no-store")
                self.assertEqual(response.headers["x-content-type-options"], "nosniff")
                self.assertEqual(report.type, "movimientos_pdf")
                self.assertEqual(report.file_url, None)
                self.assertEqual(audit.details["row_count"], 1)
                self.assertEqual(audit.details["category_id"], 1)

                with patch("app.api.v1.endpoints.reports.MOVEMENT_REPORT_MAX_ROWS", 1):
                    with self.assertRaises(HTTPException) as oversized:
                        export_movement_history_pdf(
                            date(2026, 9, 29), date(2026, 10, 31),
                            movement_status=None, item_id=None, category_id=None,
                            location_id=None, responsible_user_id=None,
                            db=db, current_user=db.get(User, 1),
                        )
                self.assertEqual(oversized.exception.status_code, 413)
                self.assertEqual(db.query(Report).count(), 1)
                self.assertEqual(db.query(AuditLog).filter(AuditLog.action == "report.export_movement_pdf").count(), 1)
        finally:
            from sqlalchemy import event
            for model in (User, Report, AuditLog):
                event.remove(model, "before_insert", set_test_timestamps)
            engine.dispose()

    def test_pdf_export_rate_limit_allows_five_and_rejects_sixth(self):
        with patch("app.services.rate_limit_service.redis_client") as client:
            client.eval.return_value = (5, 37)
            enforce_report_pdf_limit(12)

            client.eval.return_value = (6, 36)
            with self.assertRaises(HTTPException) as limited:
                enforce_report_pdf_limit(12)

        self.assertEqual(limited.exception.status_code, 429)
        self.assertEqual(limited.exception.headers["Retry-After"], "36")

    def test_pdf_export_fails_closed_when_redis_is_unavailable(self):
        with patch("app.services.rate_limit_service.redis_client") as client:
            client.eval.side_effect = RedisError("offline")
            with self.assertRaises(HTTPException) as unavailable:
                enforce_report_pdf_limit(12)

        self.assertEqual(unavailable.exception.status_code, 503)

    def test_period_windows_are_adjacent_for_week_and_month(self):
        now = datetime(2026, 10, 1, 15, 30, tzinfo=timezone.utc)
        for period in ("week", "month"):
            windows = report_windows(period, now)
            self.assertEqual(len(windows), 3)
            self.assertEqual(windows[1][2], windows[0][1])
            self.assertEqual(windows[2][2], windows[1][1])
            self.assertTrue(all(start < end for _, start, end in windows))

    def test_summary_calculates_metrics_without_persisting_aggregates(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine, tables=[
            Role.__table__, User.__table__, Category.__table__, Location.__table__, Item.__table__,
            Movement.__table__, Alert.__table__,
        ])
        now = datetime(2026, 10, 1, 15, 30, tzinfo=timezone.utc)

        def dt(day, hour=0):
            return datetime(2026, 9, day, hour, tzinfo=timezone.utc)

        try:
            with Session(engine) as db:
                db.add(Role(id=1, name="administrador"))
                db.add(User(
                    id=1, username="admin", email="admin@example.com", full_name="Admin", hashed_password="unused",
                    role_id=1, is_active=True, created_at=now, updated_at=now,
                ))
                db.add(Location(id=1, name="Taller"))
                db.add_all([
                    Item(id=1, code="TAL-1", name="Taladro", type=ItemType.HERRAMIENTA,
                         status=ItemStatus.DISPONIBLE, created_at=now, updated_at=now),
                    Item(id=2, code="HER-1", name="Llave", type=ItemType.HERRAMIENTA,
                         status=ItemStatus.DISPONIBLE, created_at=now, updated_at=now),
                ])
                db.flush()
                db.add_all([
                    Movement(id=1, item_id=1, responsible_user_id=1, location_id=1, purpose="A",
                             status=MovementStatus.CLOSED, checkout_at=dt(29, 9), checkin_at=dt(29, 13), created_at=dt(29, 9)),
                    Movement(id=2, item_id=1, responsible_user_id=1, location_id=1, purpose="B",
                             status=MovementStatus.OPEN, checkout_at=dt(30, 9), checkin_at=None, created_at=dt(30, 9)),
                    Movement(id=3, item_id=2, responsible_user_id=1, location_id=1, purpose="C",
                             status=MovementStatus.CLOSED, checkout_at=dt(25, 9), checkin_at=dt(26, 9), created_at=dt(25, 9)),
                    Movement(id=4, item_id=2, responsible_user_id=1, location_id=1, purpose="D",
                             status=MovementStatus.CLOSED, checkout_at=dt(18, 9), checkin_at=dt(19, 9), created_at=dt(18, 9)),
                    Alert(id=1, type=AlertType.SALIDA_NO_AUTORIZADA, status=AlertStatus.ACTIVA, triggered_at=dt(29, 12)),
                    Alert(id=2, type=AlertType.FALLA_DISPOSITIVO, status=AlertStatus.RESUELTA, triggered_at=dt(26, 10)),
                    Alert(id=3, type=AlertType.MANIPULACION_SENSOR, status=AlertStatus.ACTIVA, triggered_at=dt(17, 10)),
                ])
                db.commit()
                with patch("app.api.v1.endpoints.reports.datetime") as clock:
                    clock.now.return_value = now
                    result = summarize_reports("week", db)

                response = ReportSummary.model_validate(result)
                current, previous, older = response.periods
                self.assertEqual((current.checkouts, current.returns, current.incidents), (2, 1, 1))
                self.assertEqual(current.average_usage_seconds, 4 * 60 * 60)
                self.assertEqual(current.most_used_item, "Taladro")
                self.assertEqual((previous.checkouts, previous.returns, previous.incidents), (1, 1, 1))
                self.assertEqual((older.checkouts, older.returns, older.incidents), (1, 1, 1))
                self.assertEqual(db.query(Alert).count(), 3)
                self.assertEqual(db.query(Movement).count(), 4)
        finally:
            engine.dispose()

    def test_summary_requires_an_authenticated_reporting_role(self):
        def depends_on_user(dependant):
            return any(
                dependency.call is get_current_user or depends_on_user(dependency)
                for dependency in dependant.dependencies
            )

        for path in ("/summary", "/movements/pdf"):
            route = next(route for route in router.routes if route.path == path)
            self.assertTrue(depends_on_user(route.dependant), path)

    def test_pdf_export_returns_a_pdf_and_audits_report_metadata(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine, tables=[
            Role.__table__, User.__table__, Category.__table__, Location.__table__, Item.__table__,
            Movement.__table__, Alert.__table__, Report.__table__, AuditLog.__table__,
        ])
        now = datetime.now(timezone.utc)

        def set_test_timestamps(mapper, connection, target):
            if isinstance(target, (User, Report, AuditLog)):
                target.created_at = now if isinstance(target, User) else getattr(target, "created_at", None)
                if isinstance(target, Report):
                    target.generated_at = now
                if isinstance(target, AuditLog):
                    target.timestamp = now
                if isinstance(target, User):
                    target.updated_at = now

        for model in (User, Report, AuditLog):
            from sqlalchemy import event
            event.listen(model, "before_insert", set_test_timestamps)
        try:
            with Session(engine) as db:
                db.add(Role(id=1, name="administrador"))
                db.add(User(
                    id=1, username="admin", email="admin@example.com", full_name="Admin", hashed_password="unused",
                    role_id=1, is_active=True, created_at=now, updated_at=now,
                ))
                db.commit()
                with patch("app.api.v1.endpoints.reports.enforce_report_pdf_limit"):
                    response = export_summary_pdf("week", db=db, current_user=db.get(User, 1))
                report = db.query(Report).one()
                self.assertEqual(response.media_type, "application/pdf")
                self.assertTrue(response.body.startswith(b"%PDF-"))
                self.assertEqual(response.headers["cache-control"], "private, no-store")
                self.assertEqual(response.headers["pragma"], "no-cache")
                self.assertEqual(response.headers["x-content-type-options"], "nosniff")
                self.assertEqual(report.type, "resumen_week_pdf")
                audit = db.query(AuditLog).filter(AuditLog.action == "report.export_pdf").one()
                self.assertEqual(audit.entity_id, report.id)
        finally:
            from sqlalchemy import event
            for model in (User, Report, AuditLog):
                event.remove(model, "before_insert", set_test_timestamps)
            engine.dispose()


if __name__ == "__main__":
    unittest.main()