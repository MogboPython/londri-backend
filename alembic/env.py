from logging.config import fileConfig

from alembic import context
from geoalchemy2 import alembic_helpers  # registers PostGIS type comparators
from sqlalchemy import engine_from_config, pool

import app.models  # noqa: F401 — side-effect import
from app.core.config import settings
from app.models.base import Base


# Alembic Config object (gives access to alembic.ini values)
config = context.config

# Override the sqlalchemy.url from alembic.ini with the value from .env
config.set_main_option("sqlalchemy.url", settings.DATABASE_SYNC_URL)

# Set up Python logging from alembic.ini [loggers] section
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Include GeoAlchemy2 spatial tables/types in autogenerate
include_schemas = True


def include_object(obj, name, type_, reflected, compare_to):
    SUPABASE_INTERNAL_SCHEMAS = {
        "auth", "storage", "extensions", "vault", "graphql_public",
        "realtime", "supabase_functions", "supabase_migrations",
        "net", "pg_toast", "pg_catalog", "information_schema",
    }

    if type_ == "table" and name in {"spatial_ref_sys", "geometry_columns", "geography_columns"}:
        return False

    schema = getattr(obj, "schema", None)
    if schema is None:
        table = getattr(obj, "table", None)
        schema = getattr(table, "schema", None) if table is not None else None

    if schema in SUPABASE_INTERNAL_SCHEMAS:
        return False

    return True

def run_migrations_offline() -> None:
    """Run migrations without a live DB connection — emits SQL to stdout."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=include_schemas,
        include_object=include_object,
        render_item=alembic_helpers.render_item,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live DB connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=include_schemas,
            include_object=include_object,
            render_item=alembic_helpers.render_item,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
