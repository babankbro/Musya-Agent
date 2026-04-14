"""FastAPI application entrypoint for the Musya Agent backend."""
import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.config import get_settings
from src.db.pool import get_async_pool, close_async_pool, close_sync_pool
from src.routers import health, chat, ingest, test_ui, evidence, upload, documents, citation

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: init and cleanup resources."""
    s = get_settings()

    # Configure Gemini API key
    if s.GEMINI_API_KEY:
        os.environ["GEMINI_API_KEY"] = s.GEMINI_API_KEY
        os.environ["GOOGLE_API_KEY"] = s.GEMINI_API_KEY
        logger.info("Gemini API key configured")
    else:
        logger.warning("GEMINI_API_KEY not set — LLM calls will fail")

    # Init async DB pool
    try:
        await get_async_pool()
        logger.info(f"PostgreSQL pool connected to {s.DB_HOST}:{s.DB_PORT}/{s.DB_NAME}")
    except Exception as e:
        logger.error(f"Failed to connect to PostgreSQL: {e}")

    logger.info(f"Agent server starting on {s.HOST}:{s.PORT}")
    yield

    # Cleanup
    await close_async_pool()
    close_sync_pool()
    logger.info("Pools closed. Shutting down.")


app = FastAPI(
    title="Musya Agent API",
    description="Agentic AI + RAG backend for health plan document generation",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
s = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=s.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
import pathlib
static_dir = pathlib.Path(__file__).parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Routers
app.include_router(health.router)
app.include_router(chat.router)
app.include_router(ingest.router)
app.include_router(evidence.router)
app.include_router(upload.router)
app.include_router(documents.router)
app.include_router(citation.router)
app.include_router(test_ui.router)


@app.get("/")
async def root():
    return {
        "name": "Musya Agent API",
        "version": "0.1.0",
        "docs": "/docs",
        "test_ui": "/test",
    }


@app.get("/test")
async def test_ui_page():
    """Serve the standalone test UI."""
    import pathlib
    from fastapi.responses import HTMLResponse
    html_path = pathlib.Path(__file__).parent.parent / "static" / "test_ui.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"), status_code=200)


@app.get("/documents")
async def document_upload_ui_page():
    """Serve the Document & Citation Manager UI."""
    import pathlib
    from fastapi.responses import HTMLResponse
    html_path = pathlib.Path(__file__).parent.parent / "static" / "document_upload_ui.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"), status_code=200)


def run():
    """Entry point for `agent-server` script."""
    import uvicorn
    s = get_settings()
    uvicorn.run(
        "src.main:app",
        host=s.HOST,
        port=s.PORT,
        log_level=s.LOG_LEVEL,
        reload=True,
    )


if __name__ == "__main__":
    run()
