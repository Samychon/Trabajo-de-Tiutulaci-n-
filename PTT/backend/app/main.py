import asyncio

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

import app.db.base  # noqa: F401  # Importa todos los modelos para registrar relaciones SQLAlchemy
from app.api.v1.router import api_router
from app.api.deps import get_current_user, get_db
from app.core.config import get_settings
from app.ws.connection_manager import alert_manager

settings = get_settings()

app = FastAPI(title=settings.PROJECT_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.on_event("startup")
async def on_startup() -> None:
    alert_manager.bind_loop(asyncio.get_running_loop())


@app.websocket("/ws/alerts")
async def alerts_socket(websocket: WebSocket, db: Session = Depends(get_db)) -> None:
    if websocket.headers.get("origin") not in settings.ALLOWED_ORIGINS:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    try:
        token = await asyncio.wait_for(websocket.receive_text(), timeout=5)
        get_current_user(token=token, db=db)
    except WebSocketDisconnect:
        return
    except (asyncio.TimeoutError, HTTPException):
        await websocket.close(code=1008)
        return

    db.close()
    await alert_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        alert_manager.disconnect(websocket)


@app.get("/health", tags=["health"])
def health_check() -> dict:
    return {"status": "ok"}
