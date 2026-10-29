import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.ai.router import router as ai_router
from app.ingestion.router import router as ingestion_router
from app.mapping.router import router as mapping_router
from app.matching.router import router as matching_router
from app.orchestration.router import router as orchestration_router

app = FastAPI(
    title=settings.APP_NAME,
    description="AI-powered GST Reconciliation Application API",
    version="0.1.0",
    docs_url=f"{settings.API_V1_STR}/docs" if settings.DEBUG else None,
    openapi_url=f"{settings.API_V1_STR}/openapi.json" if settings.DEBUG else None,
)

if settings.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(ingestion_router, prefix=settings.API_V1_STR)
app.include_router(mapping_router, prefix=settings.API_V1_STR)
app.include_router(matching_router, prefix=settings.API_V1_STR)
app.include_router(ai_router, prefix=settings.API_V1_STR)
app.include_router(orchestration_router, prefix=settings.API_V1_STR)

# Serve static dashboard
static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_dashboard():
        return FileResponse(os.path.join(static_dir, "index.html"))


from fastapi import Response, status


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Favicon handler to prevent 404 console warnings."""
    return Response(status_code=status.HTTP_204_NO_CONTENT, media_type="image/x-icon")








@app.get("/health", tags=["Health"])

async def health_check():
    """Health check endpoint to verify service operational status."""
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "version": "0.1.0",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )

