from __future__ import annotations

import json
import logging
import os
from collections import defaultdict

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from app.database import get_sqlite_db_file_path, initialize_database
from app.routes.auth_routes import router as auth_router
from app.routes.learning_routes import router as learning_router
from app.routes.stats_routes import router as stats_router
from app.routes.word_routes import router as word_router
from app.scheduler import LearningScheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Harsh Vocabulary Intelligence System", version="1.0.0")
templates = Jinja2Templates(directory="app/templates")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class WebSocketManager:
    def __init__(self) -> None:
        self.active_connections: dict[int, set[WebSocket]] = defaultdict(set)

    async def connect(self, user_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections[user_id].add(websocket)

    def disconnect(self, user_id: int, websocket: WebSocket) -> None:
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)

    def send_to_user(self, user_id: int, payload: dict) -> None:
        # called from scheduler thread, no await available. messages are pulled in ws loop via ping endpoint fallback.
        # To keep thread-safe behavior in this simple app, we attach queued payloads on app state.
        app.state.notification_queue[user_id].append(payload)


websocket_manager = WebSocketManager()
app.state.notification_queue = defaultdict(list)
app.state.learning_scheduler = LearningScheduler(websocket_manager)


@app.on_event("startup")
def on_startup() -> None:
    initialize_database()
    sqlite_path = get_sqlite_db_file_path()
    if sqlite_path is not None:
        exists = sqlite_path.exists()
        logger.info("SQLite database path: %s", sqlite_path)
        logger.info("SQLite database file present: %s", exists)
    app.state.learning_scheduler.start()


@app.on_event("shutdown")
def on_shutdown() -> None:
    app.state.learning_scheduler.shutdown()


app.include_router(auth_router)
app.include_router(word_router)
app.include_router(learning_router)
app.include_router(stats_router)


@app.get("/", response_class=HTMLResponse)
def root(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/signup", response_class=HTMLResponse)
def signup_page(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request})


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.websocket("/ws/learning")
async def learning_ws(websocket: WebSocket, token: str = Query(...)):
    from jose import JWTError, jwt

    from app.auth import ALGORITHM, SECRET_KEY

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
    except (JWTError, TypeError, ValueError):
        await websocket.close(code=1008)
        return

    await websocket_manager.connect(user_id, websocket)
    try:
        while True:
            queued = app.state.notification_queue[user_id]
            while queued:
                await websocket.send_text(json.dumps(queued.pop(0)))
            await websocket.receive_text()
    except WebSocketDisconnect:
        websocket_manager.disconnect(user_id, websocket)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000)),
    )
