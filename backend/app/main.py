from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.api.routes import router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(title="ActPilot API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")

STATIC_DIR = Path(__file__).resolve().parent / "static"


@app.get("/privacy")
def privacy_policy() -> FileResponse:
    return FileResponse(STATIC_DIR / "privacy.html", media_type="text/html")
