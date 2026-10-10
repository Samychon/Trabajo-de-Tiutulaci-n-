from fastapi import APIRouter

from app.api.v1.endpoints import alerts, auth, devices, items, movements, reports, requests, users

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(items.router, prefix="/items", tags=["items"])
api_router.include_router(movements.router, prefix="/movements", tags=["movements"])
api_router.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
api_router.include_router(devices.router, prefix="/devices", tags=["devices"])
api_router.include_router(requests.router, prefix="/requests", tags=["warehouse-requests"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
