"""Alembic environment configuration.

Reads the URL from application settings and targets the model metadata, so
``alembic revision --autogenerate`` picks up every model change automatically.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import settings

# Importing the models package registers every table on the shared metadata.
from app.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Alembic stores this in a configparser section, whose BasicInterpolation treats
# "%" as the start of a %(name)s reference. A URL-encoded password (e.g. "%40"
# for "@") is therefore rejected with "invalid interpolation syntax". Doubling
# the percent sign escapes it; configparser un-doubles it on read-back, so
# engine_from_config still receives the correct URL.
config.set_main_option(
    "sqlalchemy.url", settings.database_url.replace("%", "%%")
)
target_metadata = Base.metadata

#: Schemas Alembic is allowed to manage. Everything else belongs to an
#: extension: PostGIS ships the ``tiger``, ``tiger_data`` and ``topology``
#: schemas, and reflecting them made autogenerate emit DROP statements for a
#: dozen tables we do not own.
MANAGED_SCHEMAS = {"public"}

#: Extension-owned tables that live in ``public`` and must never be dropped.
EXCLUDED_TABLES = {"spatial_ref_sys", "geography_columns", "geometry_columns"}


def include_name(name, type_, parent_names) -> bool:
    """Restrict reflection to schemas this project owns.

    ``None`` means "the default schema" and must be accepted: Alembic reports it
    by that ``None`` rather than by the name ``public``.
    """
    if type_ == "schema":
        return name in (None, *MANAGED_SCHEMAS)
    return True


def pin_search_path(connection) -> None:
    """Restrict the migration connection to the ``public`` schema.

    This is load-bearing, and not merely tidy. The PostGIS image leaves
    ``search_path`` as ``"$user", public, topology, tiger``, so when Alembic
    reflects with ``schema=None`` it resolves that to *everything on the search
    path* - including the Tiger geocoder's forty-odd tables. Those then appear in
    the reflected set but not in our metadata, so autogenerate reports every one
    of them as a "removed table" and emits a DROP for it.

    ``include_name`` cannot prevent that: Alembic filters reflected tables by
    schema *name*, and consults ``include_name`` (not ``include_object``) in that
    loop, while everything reachable here shares the single name ``None``. Pinning
    the search path is what actually removes them from consideration.
    """
    connection.exec_driver_sql("SET search_path TO public")


def _schema_of(obj) -> str | None:
    """Best-effort schema lookup for tables, indexes and constraints."""
    schema = getattr(obj, "schema", None)
    if schema is None:
        schema = getattr(getattr(obj, "table", None), "schema", None)
    return schema


def include_object(obj, name, type_, reflected, compare_to) -> bool:
    """Second line of defence for objects outside our schema."""
    if type_ == "table" and name in EXCLUDED_TABLES:
        return False
    if _schema_of(obj) not in (None, *MANAGED_SCHEMAS):
        return False
    return True


def run_migrations_offline() -> None:
    """Emit SQL to stdout without connecting (``alembic upgrade --sql``)."""
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_name=include_name,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        pin_search_path(connection)
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            include_name=include_name,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()

        # Managed hosts such as Supabase can leave this transaction open after
        # alembic finishes, so the final COMMIT never reaches the server and
        # the whole chain is discarded when the connection closes. Close it
        # explicitly; when alembic already committed this is a no-op.
        if connection.in_transaction():
            connection.commit()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
