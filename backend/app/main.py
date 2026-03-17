from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router
from app.db.session import init_db

import logging

logger = logging.getLogger(__name__)

app = FastAPI(title="AI News Aggregator BFF", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.on_event("startup")
def on_startup() -> None:
    try:
        init_db()
    except Exception:
        logger.exception("Database initialization failed. API can still start, but /api/news and /api/sync may fail.")
