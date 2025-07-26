"""
Main FastAPI application for the AI Assistant Platform.

This module serves as the entry point for the FastAPI application,
configuring middleware, routes, and application lifecycle events.
"""

from contextlib import asynccontextmanager
from datetime import UTC, datetime

from app.api.v1.api import api_router
from app.core.config import get_settings
from app.core.database import check_db_connection, init_db
from app.core.i18n import I18nMiddleware, i18n_manager, t
from app.core.redis_client import close_redis, init_redis
from app.core.security_middleware import setup_security_middleware
from app.core.weaviate_client import (
    check_weaviate_connection,
    close_weaviate,
    create_schema_if_not_exists,
    init_weaviate,
)
from app.services.performance_monitor import performance_monitor
from fastapi import FastAPI, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

# OpenTelemetry-Setup (disabled for testing)
# from opentelemetry import metrics, trace
# from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
# from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
# from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
# from opentelemetry.instrumentation.redis import RedisInstrumentor
# from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
# from opentelemetry.sdk.metrics import MeterProvider
# from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
# from opentelemetry.sdk.resources import Resource
# from opentelemetry.sdk.trace import TracerProvider
# from opentelemetry.sdk.trace.export import BatchSpanProcessor
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware


@asynccontextmanager
async def lifespan(_):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting AI Assistant Platform...")
    logger.info(f"Environment: {get_settings().environment}")
    logger.info(f"Debug mode: {get_settings().debug}")

    def raise_runtime_error(msg):
        raise RuntimeError(msg)

    try:
        # Initialize database
        logger.info("Initializing database...")
        init_db()
        if not check_db_connection():
            logger.error("Database connection failed")
            raise_runtime_error("Database connection failed")
        logger.info("Database initialized successfully")

        # Initialize Redis with graceful degradation
        logger.info("Initializing Redis...")
        redis_client = await init_redis()
        if redis_client is None:
            logger.warning("Redis not available - continuing without caching")
        else:
            logger.info("Redis initialized successfully")

        # Initialize Weaviate
        logger.info("Initializing Weaviate...")
        init_weaviate()
        if not check_weaviate_connection():
            logger.error("Weaviate connection failed")
            raise_runtime_error("Weaviate connection failed")
        create_schema_if_not_exists()
        logger.info("Weaviate initialized successfully")

        logger.info("All services initialized successfully")

    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to initialize services: {exc}")

        def raise_inner(exc=exc):
            raise RuntimeError("Failed to initialize services: " + str(exc))

        raise_inner()

    yield

    # Shutdown
    logger.info("Shutting down AI Assistant Platform...")
    try:
        await close_redis()
        close_weaviate()
        logger.info("All services closed successfully")
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error during shutdown: {e}")


def configure_opentelemetry(app, db_engine=None, redis_client=None):
    # OpenTelemetry disabled for testing
    pass
    # resource = Resource.create({
    #     "service.name": os.getenv("OTEL_SERVICE_NAME", "ai-assistant-platform"),
    #     "service.version": get_settings().app_version,
    #     "deployment.environment": get_settings().environment,
    # })
    # # Tracing
    # tracer_provider = TracerProvider(resource=resource)
    # trace.set_tracer_provider(tracer_provider)
    # otlp_exporter = OTLPSpanExporter(endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"), insecure=True)
    # span_processor = BatchSpanProcessor(otlp_exporter)
    # tracer_provider.add_span_processor(span_processor)
    # # Metrics
    # metric_exporter = OTLPMetricExporter(endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"), insecure=True)
    # metric_reader = PeriodicExportingMetricReader(metric_exporter)
    # meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    # metrics.set_meter_provider(meter_provider)
    # # Instrumentierung
    # FastAPIInstrumentor.instrument_app(app)
    # if db_engine is not None:
    #     SQLAlchemyInstrumentor().instrument(engine=db_engine)
    # if redis_client is not None:
    #     RedisInstrumentor().instrument()


def create_application() -> FastAPI:
    """Create and configure the FastAPI application."""

    # Configure logging to console for now (file logging disabled due to permission issues)
    logger.add(
        lambda msg: print(msg, end=""),
        level=get_settings().log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} - {message}",
    )

    # Create FastAPI app
    app = FastAPI(
        title="AI Assistant Platform",
        version=get_settings().app_version,
        description="AI Assistant Platform with multiple assistants and extensive tool support",
        docs_url="/docs" if get_settings().debug else None,
        redoc_url="/redoc" if get_settings().debug else None,
        openapi_url="/openapi.json" if get_settings().debug else None,
        lifespan=lifespan,
    )
    # OpenTelemetry initialisieren (disabled for testing)
    # if not get_settings().debug or os.getenv("DISABLE_OTEL", "false").lower() != "true":
    #     from app.core.database import engine
    #     from app.core.redis_client import redis_client
    #     configure_opentelemetry(app, db_engine=engine, redis_client=redis_client)

    # Setup security middleware first
    setup_security_middleware(app)

    # Add CORS middleware with secure configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=(
            ["*"]
            if get_settings().debug
            else ["localhost", "127.0.0.1", "yourdomain.com"]
        ),
    )

    # Add i18n middleware
    app.add_middleware(I18nMiddleware, i18n_manager=i18n_manager)

    # Add session middleware for OAuth
    app.add_middleware(SessionMiddleware, secret_key=get_settings().secret_key)

    # Start performance monitoring if enabled
    if performance_monitor.monitoring_enabled:
        performance_monitor.start_monitoring()

    # Add exception handlers
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(_, exc: StarletteHTTPException):
        """Handle HTTP exceptions."""
        logger.warning(f"HTTP {exc.status_code}: {exc.detail}")
        # Translate error message
        translated_detail = t(
            f"errors.{exc.detail.lower().replace(' ', '_')}",
            None,
            fallback=exc.detail,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": translated_detail, "status_code": exc.status_code},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_, exc: RequestValidationError):
        """Handle validation exceptions."""
        logger.warning(f"Validation error: {exc.errors()}")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": exc.errors(), "status_code": 422},
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(_, exc: Exception):
        """Handle general exceptions."""
        logger.error(f"Unhandled exception: {exc}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error", "status_code": 500},
        )

    # Health check endpoint
    @app.get("/health")
    async def health_check():
        """Health check endpoint with service status."""
        from app.core.redis_client import check_redis_connection, get_redis_info

        # Check Redis status
        try:
            redis_connected = await check_redis_connection()
            redis_info = await get_redis_info()
            redis_status = "connected" if redis_connected else "unavailable"
        except Exception as e:
            redis_status = "error"
            redis_info = {"error": str(e)}

        return {
            "status": "healthy",
            "app_name": get_settings().app_name,
            "version": get_settings().app_version,
            "environment": get_settings().environment,
            "timestamp": datetime.now(UTC).isoformat(),
            "services": {"redis": {"status": redis_status, "info": redis_info}},
        }

    # Config endpoint for frontend (must be before API routers)
    @app.get("/api/config")
    async def get_config():
        """Get application configuration for frontend."""
        return {
            "apiUrl": "/api",
            "wsUrl": get_settings().ws_url,
            "isDevelopment": get_settings().debug,
            "isProduction": not get_settings().debug,
            "enableDebug": get_settings().debug,
            "wsEndpoints": {
                "chat": "/api/v1/chat/ws/",
                "notifications": "/api/v1/ws/notifications",
            },
            "apiEndpoints": {
                "auth": "/api/v1/auth",
                "users": "/api/v1/users",
                "conversations": "/api/v1/conversations",
                "chat": "/api/v1/chat",
                "tools": "/api/v1/tools",
                "assistants": "/api/v1/assistants",
                "knowledge": "/api/v1/knowledge",
                "health": "/api/v1/health",
            },
        }

    # Add missing endpoints for frontend compatibility (must be before API routers)
    @app.get("/api/assistants")
    async def get_assistants_legacy():
        """Legacy assistants endpoint."""
        return {"message": "Use /api/v1/assistants instead"}

    @app.get("/api/knowledge/documents")
    async def get_knowledge_documents_legacy():
        """Legacy knowledge documents endpoint."""
        return {"message": "Use /api/v1/knowledge/documents instead"}

    @app.get("/api/ai/models")
    async def get_ai_models_legacy():
        """Legacy AI models endpoint."""
        return {"message": "Use /api/v1/ai/models instead"}

    # Initialize OAuth
    # oauth_service.oauth.init_app(app)  # Commented out - Starlette OAuth doesn't need init_app

    # Add routes
    app.include_router(api_router, prefix="/api/v1")

    # Add legacy routes for frontend compatibility - REMOVED DUPLICATE
    # app.include_router(api_router, prefix="/api")  # This was causing 307 redirects

    # Root endpoint
    @app.get("/")
    async def root():
        """Root endpoint."""
        return {
            "message": "Welcome to AI Assistant Platform",
            "version": get_settings().app_version,
            "docs": (
                "/docs"
                if get_settings().debug
                else "Documentation disabled in production"
            ),
        }

    return app


# Create application instance
app = create_application()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=get_settings().host,
        port=get_settings().port,
        reload=get_settings().debug,
        log_level=get_settings().log_level.lower(),
    )
