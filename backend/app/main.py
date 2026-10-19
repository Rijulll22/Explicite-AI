import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import update

from app.config import settings
from app.database import init_db

logger = logging.getLogger(__name__)


async def _recover_stale_jobs() -> None:
    """Mark any 'running' jobs as 'failed' — they were killed by a restart."""
    from app.database import get_session_factory
    from app.models.analysis import AnalysisJob

    factory = get_session_factory()
    async with factory() as db:
        try:
            await db.execute(
                update(AnalysisJob)
                .where(AnalysisJob.status == "running")
                .values(
                    status="failed",
                    failed_at=datetime.now(timezone.utc),
                    failure_reason="Server restarted during analysis — please resubmit",
                )
                .execution_options(synchronize_session=False)
            )
            await db.commit()
        except Exception:
            logger.exception("Failed to recover stale analysis jobs at startup")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db(settings.DATABASE_URL)
    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    await _recover_stale_jobs()
    yield


app = FastAPI(
    title="Explicite AI",
    description="AI-powered explainable code review and programming-learning platform.",
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
from app.api.auth import router as auth_router
from app.api.projects import router as projects_router
from app.api.issues import router as issues_router
from app.api.learning import router as learning_router, rec_router as learning_rec_router
from app.api.analysis import router as analysis_router
from app.api.ai import router as ai_router
from app.api.fixes import router as fixes_router

API_PREFIX = "/api/v1"

app.include_router(auth_router, prefix=API_PREFIX)
app.include_router(projects_router, prefix=API_PREFIX)
app.include_router(issues_router, prefix=API_PREFIX)
app.include_router(learning_router, prefix=API_PREFIX)
app.include_router(learning_rec_router, prefix=API_PREFIX)
app.include_router(analysis_router, prefix=API_PREFIX)
app.include_router(ai_router, prefix=API_PREFIX)
app.include_router(fixes_router, prefix=API_PREFIX)


@app.get("/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok", "version": settings.APP_VERSION}
