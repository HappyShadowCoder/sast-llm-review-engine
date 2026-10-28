from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import engine, Base, init_db, close_db
from .routers import health_router, webhooks_router, analytics_router, reviews_router

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("aicr.api-gateway")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up API Gateway...")
    await init_db()
    yield
    logger.info("Shutting down API Gateway...")
    await close_db()


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Code Reviewer API Gateway",
        description="Multi-VCS Webhook Gateway, REST API, and Review Coordinator",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "*",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(webhooks_router)
    app.include_router(analytics_router)
    app.include_router(reviews_router)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=settings.PORT, reload=True)
