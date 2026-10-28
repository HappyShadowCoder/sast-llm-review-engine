import os
from alembic.config import Config
from alembic import command
from pathlib import Path


def test_alembic_upgrade_downgrade(tmp_path: Path):
    db_file = tmp_path / "migration_test.db"
    sqlite_url = f"sqlite:///{db_file}"
    sqlite_async_url = f"sqlite+aiosqlite:///{db_file}"

    # Point alembic to test DB
    alembic_ini_path = Path(__file__).resolve().parents[1] / "alembic.ini"
    cfg = Config(str(alembic_ini_path))
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "alembic"))
    cfg.set_main_option("sqlalchemy.url", sqlite_async_url)

    # Set environment variables for Alembic env.py
    os.environ["DATABASE_URL"] = sqlite_async_url
    os.environ["DATABASE_URL_SYNC"] = sqlite_url

    # Upgrade to head
    command.upgrade(cfg, "head")

    # Downgrade to base
    command.downgrade(cfg, "base")

    # Upgrade back to head to verify re-application
    command.upgrade(cfg, "head")
