"""
GTM Engine API Service

FastAPI application providing query endpoints for the UI.
"""

import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from shared.utils.config import get_settings
from shared.utils.logging import bind_request_context, clear_context, get_logger, setup_logging

setup_logging()
logger = get_logger("api_service")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    logger.info("Starting API service", debug=settings.debug)
    yield
    logger.info("Shutting down API service")


app = FastAPI(
    title="GTM Engine API",
    description="Job GTM Intelligence Platform API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next) -> Response:
    """Add request_id to all requests and responses."""
    request_id = str(uuid.uuid4())
    bind_request_context(request_id)
    
    response = await call_next(request)
    response.headers["X-Request-Id"] = request_id
    
    clear_context()
    return response


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "api_service",
        "version": "0.1.0",
    }



# Import and include routers
from apps.api_service.routers import jobs, companies, skills, search

app.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
app.include_router(companies.router, prefix="/companies", tags=["companies"])
app.include_router(skills.router, prefix="/skills", tags=["skills"])
app.include_router(search.router, prefix="/search", tags=["search"])


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "apps.api_service.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )
