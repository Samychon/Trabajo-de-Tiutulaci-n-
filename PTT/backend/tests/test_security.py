import asyncio
import time
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException, WebSocketDisconnect
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.v1.endpoints.alerts import deactivate_alert, router as alerts_router
from app.api.v1.endpoints.movements import authorize_movement, router as movements_router
from app.core.security import device_request_message, encrypt_device_secret, sign_device_payload
from app.core.zero_trust import verify_device_request
from app.db.session import Base
from app.main import alerts_socket, settings
from app.models.alert import DeactivationMethod
from app.models.device import Device, DeviceRequestNonce, DeviceType
from app.models.location import Location
from app.schemas.alert import AlertDeactivateRequest
from app.schemas.auth import MovementAuthorizationRequest
from app.schemas.user import UserCreate, UserRead
from app.ws.connection_manager import alert_manager
from pydantic import ValidationError


class SecurityTests(unittest.TestCase):
    def test_seeded_local_email_can_be_read_but_not_created(self):
        profile = UserRead.model_validate(SimpleNamespace(
            id=1, username="admin", email="admin@ipi2.local", full_name="Administrador", is_active=True,
            role_id=1, role_name="administrador",
        ))
        self.assertEqual(profile.email, "admin@ipi2.local")
        with self.assertRaises(ValidationError):
            UserCreate(username="new", email="invalid", full_name="Nuevo", password="password", role_id=1)

    def test_sensitive_routes_require_a_session(self):
        for router, path in (
            (movements_router, "/{movement_id}/authorize"),
            (alerts_router, "/{alert_id}/deactivate"),
        ):
            route = next(route for route in router.routes if route.path == path)

            def calls_user_auth(dependant):
                return any(
                    dependency.call is get_current_user or calls_user_auth(dependency)
                    for dependency in dependant.dependencies
                )

            self.assertTrue(calls_user_auth(route.dependant), path)

    def test_unattested_biometric_claims_are_rejected(self):
        with self.assertRaises(HTTPException) as movement_error:
            authorize_movement(1, MovementAuthorizationRequest(method="fingerprint", sensor_slot_id="1"), MagicMock())
        self.assertEqual(movement_error.exception.status_code, 403)

        with self.assertRaises(HTTPException) as alert_error:
            deactivate_alert(1, AlertDeactivateRequest(method=DeactivationMethod.FINGERPRINT), MagicMock())
        self.assertEqual(alert_error.exception.status_code, 403)

    def test_websocket_rejects_untrusted_origin(self):
        websocket = MagicMock(headers={"origin": "https://other.example"})
        websocket.close = AsyncMock()
        asyncio.run(alerts_socket(websocket, db=MagicMock()))
        websocket.accept.assert_not_called()
        websocket.close.assert_awaited_once_with(code=1008)

    def test_websocket_rejects_invalid_access_token(self):
        websocket = MagicMock(headers={"origin": settings.ALLOWED_ORIGINS[0]})
        websocket.accept = AsyncMock()
        websocket.receive_text = AsyncMock(return_value="invalid")
        websocket.close = AsyncMock()
        asyncio.run(alerts_socket(websocket, db=MagicMock()))
        websocket.close.assert_awaited_once_with(code=1008)
        self.assertNotIn(websocket, alert_manager._connections)

    def test_websocket_registers_only_after_valid_access_token(self):
        websocket = MagicMock(headers={"origin": settings.ALLOWED_ORIGINS[0]})
        websocket.accept = AsyncMock()
        websocket.receive_text = AsyncMock(side_effect=["access-token", WebSocketDisconnect()])
        with patch("app.main.get_current_user") as authenticate:
            asyncio.run(alerts_socket(websocket, db=MagicMock()))
        authenticate.assert_called_once()
        self.assertNotIn(websocket, alert_manager._connections)

    def test_signed_device_event_rejects_tampering_and_replay(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine, tables=[Location.__table__, Device.__table__, DeviceRequestNonce.__table__])
        secret = "test-device-secret"
        device_id = "test-reader"
        timestamp = str(int(time.time()))
        nonce = "a" * 32
        path = "/api/v1/devices/events/rfid"
        body = b'{"tag_code":"TAG-001","event_type":"salida"}'

        def signed_request(content, request_nonce):
            message = device_request_message(device_id, timestamp, request_nonce, "POST", path, body)
            signature = sign_device_payload(secret, message)
            request = SimpleNamespace(method="POST", url=SimpleNamespace(path=path), body=AsyncMock(return_value=content))
            return request, signature

        with Session(engine) as db:
            db.add(Device(
                device_uid=device_id,
                type=DeviceType.RFID_READER,
                secret_encrypted=encrypt_device_secret(secret),
                registered_at=datetime.now(timezone.utc),
            ))
            db.commit()
            request, signature = signed_request(body, nonce)
            asyncio.run(verify_device_request(request, device_id, timestamp, signature, nonce, db))

            with self.assertRaises(HTTPException) as repeated:
                asyncio.run(verify_device_request(request, device_id, timestamp, signature, nonce, db))
            self.assertEqual(repeated.exception.status_code, 401)

            tampered_request, valid_signature = signed_request(body.replace(b"TAG-001", b"TAG-002"), "b" * 32)
            with self.assertRaises(HTTPException) as tampered:
                asyncio.run(verify_device_request(tampered_request, device_id, timestamp, valid_signature, "b" * 32, db))
            self.assertEqual(tampered.exception.status_code, 401)

        engine.dispose()


if __name__ == "__main__":
    unittest.main()