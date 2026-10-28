from importlib.resources import as_file, files
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import URL, Engine, create_engine, event
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.pool import ConnectionPoolEntry


def open_database(path: Path) -> Engine:
    """
    Open an engine on the SQLite file at the path, and migrate the file to the latest schema. Each connection checks
    foreign keys and writes ahead to a log.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(URL.create("sqlite", database=str(path)))

    @event.listens_for(engine, "connect")
    def configure_connection(dbapi_connection: DBAPIConnection, connection_record: ConnectionPoolEntry) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.close()

    with as_file(files("agent_hud") / "migrations") as migrations, engine.begin() as connection:
        config = Config()
        config.set_main_option("script_location", str(migrations))
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    return engine
