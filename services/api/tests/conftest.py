"""Shared pytest fixtures.

Database-backed tests run against a real PostgreSQL instance because the suite
exercises PostGIS geometry, array columns and filtered aggregates that SQLite
cannot represent. The database is created on demand and torn down at the end of
the session; when no server is reachable the whole module skips rather than
failing, so pure-logic tests stay runnable anywhere.
"""

from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.models import Base
from app.models.enums import (
    HolderEntityType,
    LeaseStatus,
    LeaseType,
    LicenceType,
    MineralCategory,
    ObligationCategory,
    Recurrence,
    RoyaltyBasis,
)
from app.models.holder import LeaseHolder
from app.models.lease import Lease
from app.models.licence import Licence
from app.models.mineral import Mineral
from app.models.obligation import Obligation

TEST_DATABASE_SUFFIX = "_test"


def _test_urls() -> tuple[str, str]:
    """Return (admin_url, test_url) derived from the configured database URL."""
    url = make_url(settings.database_url)
    admin_url = url.set(database="postgres")
    test_database = f"{url.database or 'mining_governance'}{TEST_DATABASE_SUFFIX}"
    test_url = url.set(database=test_database)
    return admin_url.render_as_string(hide_password=False), test_url


@pytest.fixture(scope="session")
def engine() -> Generator[Engine, None, None]:
    """Create the test database and schema once per session."""
    admin_url, test_url = _test_urls()
    test_database = make_url(test_url).database

    try:
        admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
        with admin_engine.connect() as connection:
            exists = connection.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": test_database},
            )
            if not exists:
                # Identifier is derived from configuration, not user input.
                connection.execute(text(f'CREATE DATABASE "{test_database}"'))
        admin_engine.dispose()
    except Exception as error:  # pragma: no cover - environment dependent
        pytest.skip(f"PostgreSQL unavailable ({error}); set DATABASE_URL to run DB tests")

    test_engine = create_engine(test_url, pool_pre_ping=True)

    with test_engine.begin() as connection:
        for extension in ("postgis", "pg_trgm"):
            connection.execute(text(f"CREATE EXTENSION IF NOT EXISTS {extension}"))

    Base.metadata.drop_all(test_engine)
    Base.metadata.create_all(test_engine)

    yield test_engine

    Base.metadata.drop_all(test_engine)
    test_engine.dispose()


@pytest.fixture
def session(engine: Engine) -> Generator[Session, None, None]:
    """A session wrapped in a transaction that is rolled back after each test."""
    connection = engine.connect()
    transaction = connection.begin()
    # create_savepoint keeps the outer transaction open across session.commit(),
    # so tests that exercise committing endpoints still leave no residue.
    factory = sessionmaker(bind=connection, join_transaction_mode="create_savepoint")
    db = factory()
    try:
        yield db
    finally:
        db.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(session: Session):
    """A TestClient whose requests share the test's rolled-back session."""
    from fastapi.testclient import TestClient

    from app.core.db import get_db
    from app.main import app

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Data builders
# ---------------------------------------------------------------------------
@pytest.fixture
def today() -> date:
    return date.today()


@pytest.fixture
def mineral(session: Session) -> Mineral:
    entity = Mineral(
        code="TEST_IRON",
        name="Test Iron Ore",
        category=MineralCategory.MAJOR,
        royalty_basis=RoyaltyBasis.AD_VALOREM,
        royalty_rate=Decimal("15.0"),
        royalty_unit="percent_of_sale_value",
    )
    session.add(entity)
    session.flush()
    return entity


@pytest.fixture
def holder(session: Session) -> LeaseHolder:
    entity = LeaseHolder(
        name="Test Mining Company",
        entity_type=HolderEntityType.COMPANY,
        registration_number="TEST-CIN-0001",
        state="Karnataka",
    )
    session.add(entity)
    session.flush()
    return entity


@pytest.fixture
def lease(session: Session, holder: LeaseHolder, mineral: Mineral, today: date) -> Lease:
    """A healthy active concession with a surveyed square boundary."""
    from app.services import geo

    entity = Lease(
        lease_number="ML/TEST/2020/0001",
        name="Test Iron Ore Block",
        lease_type=LeaseType.MINING_LEASE,
        status=LeaseStatus.ACTIVE,
        holder_id=holder.id,
        mineral_id=mineral.id,
        district="Vijayanagara",
        state="Karnataka",
        area_hectares=Decimal("100.0"),
        grant_date=today - timedelta(days=1000),
        effective_from=today - timedelta(days=1000),
        effective_to=today + timedelta(days=1000),
    )
    entity.boundary = geo.geojson_to_multipolygon(
        {
            "type": "Polygon",
            "coordinates": [
                [
                    [76.38, 15.26],
                    [76.40, 15.26],
                    [76.40, 15.28],
                    [76.38, 15.28],
                    [76.38, 15.26],
                ]
            ],
        }
    )
    entity.centroid = geo.geojson_to_point({"type": "Point", "coordinates": [76.39, 15.27]})
    session.add(entity)
    session.flush()
    return entity


@pytest.fixture
def monthly_rule(session: Session) -> Obligation:
    entity = Obligation(
        code="TEST_MONTHLY_RETURN",
        title="Monthly production return",
        category=ObligationCategory.RETURN_FILING,
        legal_reference="Test Rule 1",
        recurrence=Recurrence.MONTHLY,
        due_days_after_period_end=15,
        fiscal_year_end_month=3,
    )
    session.add(entity)
    session.flush()
    return entity


@pytest.fixture
def annual_rule(session: Session) -> Obligation:
    entity = Obligation(
        code="TEST_ANNUAL_RETURN",
        title="Annual return",
        category=ObligationCategory.RETURN_FILING,
        legal_reference="Test Rule 2",
        recurrence=Recurrence.ANNUAL,
        due_days_after_period_end=92,
        fiscal_year_end_month=3,
    )
    session.add(entity)
    session.flush()
    return entity


@pytest.fixture
def valid_licence(session: Session, lease: Lease, today: date) -> Licence:
    entity = Licence(
        lease_id=lease.id,
        licence_type=LicenceType.ENVIRONMENTAL_CLEARANCE,
        authority="Test Authority",
        reference_number="DEMO/EC",
        valid_from=today - timedelta(days=365),
        valid_to=today + timedelta(days=365),
    )
    session.add(entity)
    session.flush()
    return entity


def make_unique_reference(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"
