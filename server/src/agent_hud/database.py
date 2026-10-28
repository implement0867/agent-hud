from importlib.resources import as_file, files
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import URL, Engine, create_engine, event
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.pool import ConnectionPoolEntry


def open_database(path: Path) -> Engine:
    """
    The engine on the SQLite file at the path, migrated to the latest schema. Each connection checks foreign keys,
    writes ahead to a log, syncs to disk at each checkpoint of the log, and waits up to 5 s for another's lock.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(URL.create("sqlite", database=str(path)))

    @event.listens_for(engine, "connect")
    def configure_connection(dbapi_connection: DBAPIConnection, connection_record: ConnectionPoolEntry) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.execute("PRAGMA synchronous = NORMAL")
        cursor.execute("PRAGMA busy_timeout = 5000")
        cursor.close()

    with as_file(files("agent_hud") / "migrations") as migrations, engine.begin() as connection:
        config = Config()
        config.set_main_option("script_location", str(migrations))
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    return engine
