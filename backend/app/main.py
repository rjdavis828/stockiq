from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import admin, alerts, fundamentals, ohlcv, scans, tickers, ws as ws_routes
from app.auth import auth_backend, fastapi_users
from app.config import settings
from app.schemas.auth import UserCreate, UserRead, UserUpdate


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="Stock Analysis Platform",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins if hasattr(settings, "cors_origins") else ["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Auth ---
app.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/api/v1/auth/jwt",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/api/v1/auth",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/api/v1/users",
    tags=["users"],
)

# --- Domain routes ---
app.include_router(tickers.router, prefix="/api/v1")
app.include_router(ohlcv.router, prefix="/api/v1")
app.include_router(scans.router, prefix="/api/v1")
app.include_router(alerts.router, prefix="/api/v1")
app.include_router(fundamentals.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(ws_routes.router)


@app.get("/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok"}
