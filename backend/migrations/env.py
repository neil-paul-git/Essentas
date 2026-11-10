"""Alembic environment: how migrations connect to the database.

The URL comes from app Settings (DATABASE_URL in backend/.env), so it lives in one place.
A sqlalchemy.url set on the Alembic config wins, which is how tests point at a temp DB.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool
from sqlmodel import SQLModel

import app.models  # noqa: F401  (registers every table on SQLModel.metadata)
from app.core.config import get_settings

config = context.config

if config.config_file_name is not None:
    # Keep the app's own loggers working when Alembic runs inside pytest.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = SQLModel.metadata


def _database_url() -> str:
    # Passed straight to SQLAlchemy, never written back into the config:
    # ConfigParser treats "%" as interpolation, and URL-encoded passwords contain "%".
    return config.get_main_option("sqlalchemy.url") or get_settings().database_url


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of running it (alembic upgrade head --sql)."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Connect to the database and run migrations."""
    engine = create_engine(_database_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Autogenerate ALTERs inside batch_alter_table(). On Postgres that's a plain
            # ALTER TABLE; on SQLite (our migration tests) Alembic rebuilds the table,
            # because SQLite can't ALTER constraints such as foreign keys.
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
