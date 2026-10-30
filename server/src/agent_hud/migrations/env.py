from alembic import context
from sqlalchemy import URL, Connection, create_engine

from agent_hud.settings import Settings
from agent_hud.tables import Base


def run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=Base.metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


# open_database passes its connection; the alembic command line, which has none, opens the app's own database.
match context.config.attributes.get("connection"):
    case Connection() as connection:
        run_migrations(connection)
    case None:
        path = Settings().database_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with create_engine(URL.create("sqlite", database=str(path))).begin() as connection:
            run_migrations(connection)
    case other:
        raise TypeError(f"the alembic connection is a {type(other).__name__}, not a SQLAlchemy Connection")
