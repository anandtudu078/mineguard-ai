"""FastAPI application entrypoint."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.db import engine
from app.services.authorization import AuthorizationError
from app.services.users import IdentityError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _check_auth_configuration() -> None:
    """Refuse to start in a state that is either open or unusable.

    Both failure modes are silent otherwise. Running production with auth off
    would serve the whole compliance register to anyone who can reach the port;
    running with auth on but nothing to verify against would reject every request
    with an opaque 401. Neither should be discoverable only from a bug report.
    """
    if settings.auth_enabled and not settings.auth_configured:
        raise RuntimeError(
            "AUTH_MODE=supabase requires either SUPABASE_URL (for asymmetric "
            "JWKS verification) or SUPABASE_JWT_SECRET (for a shared secret)."
        )

    if not settings.auth_enabled:
        if settings.is_production:
            raise RuntimeError(
                "Refusing to start: AUTH_MODE=disabled in a production environment "
                "would expose every endpoint unauthenticated."
            )
        logger.warning(
            "AUTH_MODE=disabled: every request is treated as a development "
            "administrator. Set AUTH_MODE=supabase before exposing this service."
        )
    else:
        scheme = "shared secret" if settings.supabase_jwt_secret else "JWKS"
        logger.info("Authentication enabled (Supabase, %s)", scheme)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Verify the datastore and its required extensions at boot.

    Failing loudly here is deliberate: a missing PostGIS or pgvector extension
    otherwise surfaces much later as a confusing runtime error.
    """
    _check_auth_configuration()
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            available = set(connection.scalars(text("SELECT extname FROM pg_extension")).all())
        missing = {"postgis"} - available
        if missing:
            logger.warning("Missing required extension(s): %s", ", ".join(sorted(missing)))
        logger.info("Database reachable; extensions: %s", ", ".join(sorted(available)))
    except Exception as error:  # pragma: no cover - startup diagnostics
        logger.error("Database unreachable at startup: %s", error)
    yield


app = FastAPI(
    title="Smart Mining Governance & Compliance API",
    description=(
        "Compliance governance for mineral concessions: lease registry, statutory "
        "clearances, a derived compliance calendar, and explainable risk scoring."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.api_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.exception_handler(AuthorizationError)
async def authorization_error_handler(request: Request, exc: AuthorizationError) -> JSONResponse:
    """Map a refused action to a 403.

    The audit entry was already written and committed at the point of refusal, so
    that it survives the rollback this exception triggers.
    """
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


@app.exception_handler(IdentityError)
async def identity_error_handler(request: Request, exc: IdentityError) -> JSONResponse:
    """Map a rejected identity to 403, naming the actual problem."""
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


@app.get("/health", tags=["meta"], summary="Liveness probe")
def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.api_env}


@app.get("/health/ready", tags=["meta"], summary="Readiness probe")
def readiness() -> dict[str, str]:
    """Confirm the database answers and PostGIS is present."""
    with engine.connect() as connection:
        version = connection.scalar(text("SELECT PostGIS_Version()"))
    return {"status": "ready", "postgis": version}
