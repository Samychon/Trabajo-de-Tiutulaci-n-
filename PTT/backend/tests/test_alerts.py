import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from app.api.deps import get_current_user
from app.api.v1.endpoints.alerts import deactivate_alert, router
from app.models.alert import AlertStatus, AlertType, DeactivationMethod
from app.schemas.alert import AlertDeactivateRequest, AlertRead
from app.services.alert_service import raise_unauthorized_exit_alert
from pydantic import ValidationError


class AlertTests(unittest.TestCase):
    def test_resolution_notes_match_database_limit(self):
        payload = AlertDeactivateRequest(method=DeactivationMethod.DASHBOARD, resolution_notes="x" * 500)
        self.assertEqual(len(payload.resolution_notes), 500)
        with self.assertRaises(ValidationError):
            AlertDeactivateRequest(method=DeactivationMethod.DASHBOARD, resolution_notes="x" * 501)

    def test_alert_read_includes_related_labels_without_persisted_copies(self):
        alert = SimpleNamespace(
            id=5,
            type=AlertType.SALIDA_NO_AUTORIZADA,
            item_id=2,
            movement_id=None,
            device_id=3,
            status=AlertStatus.ACTIVA,
            triggered_at=datetime.now(timezone.utc),
            resolved_at=None,
            item_name="Taladro",
            device_uid="reader-01",
            resolved_by_name=None,
            resolution_notes=None,
        )

        response = AlertRead.model_validate(alert)

        self.assertEqual(response.item_name, "Taladro")
        self.assertEqual(response.device_uid, "reader-01")
        self.assertIsNone(response.resolved_by_name)

    def test_alert_routes_require_authentication(self):
        def requires_user(dependant):
            return any(
                dependency.call is get_current_user or requires_user(dependency)
                for dependency in dependant.dependencies
            )

        for path in ("", "/{alert_id}/deactivate"):
            route = next(route for route in router.routes if route.path == path)
            self.assertTrue(requires_user(route.dependant), path)

    def test_deactivation_and_audit_share_one_commit(self):
        admin = SimpleNamespace(
            id=9, is_active=True, hashed_password="hashed", role=SimpleNamespace(name="administrador")
        )
        alert = SimpleNamespace(
            id=5, status=AlertStatus.ACTIVA, resolved_by_user_id=None, resolved_at=None,
            deactivation_method=None, resolution_notes=None,
        )
        db = MagicMock()
        alert_query = MagicMock()
        alert_query.filter.return_value.with_for_update.return_value.first.return_value = alert
        user_query = MagicMock()
        user_query.filter.return_value.first.return_value = admin
        db.query.side_effect = lambda model: alert_query if model.__name__ == "Alert" else user_query

        with patch("app.api.v1.endpoints.alerts.verify_password", return_value=True), patch(
            "app.api.v1.endpoints.alerts.record_audit"
        ) as audit:
            result = deactivate_alert(
                5,
                AlertDeactivateRequest(
                    method=DeactivationMethod.DASHBOARD,
                    username="admin",
                    password="verified",
                    resolution_notes="Sensor inspeccionado",
                ),
                db=db,
            )

        self.assertIs(result, alert)
        self.assertEqual(alert.status, AlertStatus.RESUELTA)
        self.assertEqual(alert.resolved_by_user_id, admin.id)
        self.assertEqual(alert.resolution_notes, "Sensor inspeccionado")
        db.commit.assert_called_once()
        audit.assert_called_once_with(
            db, user_id=admin.id, action="alert.deactivate", entity_type="alert", entity_id=alert.id, commit=False
        )

    def test_new_alert_commits_before_websocket_broadcast(self):
        device = SimpleNamespace(id=7)
        item = SimpleNamespace(id=2)
        alert = SimpleNamespace(id=15, item_id=item.id)
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = item
        order = []

        def add_alert(value):
            value.id = alert.id
            value.item_id = item.id

        db.add.side_effect = add_alert
        db.flush.side_effect = lambda: order.append("flush")
        db.commit.side_effect = lambda: order.append("commit")
        with patch("app.services.alert_service.Alert", return_value=alert), patch(
            "app.services.alert_service.record_audit", side_effect=lambda *args, **kwargs: order.append("audit")
        ) as audit, patch(
            "app.services.alert_service.alert_manager.broadcast_sync", side_effect=lambda message: order.append("broadcast")
        ):
            result = raise_unauthorized_exit_alert(db, device=device, tag_code="TAG-2")

        self.assertIs(result, alert)
        self.assertEqual(order, ["flush", "audit", "commit", "broadcast"])
        audit.assert_called_once_with(
            db, device_id=device.id, action="alert.trigger", entity_type="alert", entity_id=alert.id, commit=False
        )

    def test_biometric_deactivation_remains_fail_closed(self):
        with self.assertRaises(HTTPException) as denied:
            deactivate_alert(
                5, AlertDeactivateRequest(method=DeactivationMethod.FINGERPRINT), db=MagicMock()
            )
        self.assertEqual(denied.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()