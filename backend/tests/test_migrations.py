"""Migrations run against a throwaway SQLite file, never against Supabase."""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect

BACKEND_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture
def alembic_config(tmp_path: Path) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    return config


def _table_names(url: str) -> list[str]:
    engine = create_engine(url)
    try:
        return inspect(engine).get_table_names()
    finally:
        engine.dispose()  # release the file so Windows can delete tmp_path


def test_migration_history_has_single_head(alembic_config: Config) -> None:
    """Two heads means two migrations branched from the same parent and need merging."""
    assert len(ScriptDirectory.from_config(alembic_config).get_heads()) == 1


def test_upgrade_then_downgrade(alembic_config: Config) -> None:
    url = alembic_config.get_main_option("sqlalchemy.url")

    command.upgrade(alembic_config, "head")
    assert "alembic_version" in _table_names(url)

    command.downgrade(alembic_config, "base")


def test_models_match_migrations(alembic_config: Config) -> None:
    """Fails if a model changed without a matching migration (same as `alembic check`)."""
    command.upgrade(alembic_config, "head")
    command.check(alembic_config)
