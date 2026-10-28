from typing import Literal

from alembic import context
from alembic.autogenerate.api import AutogenContext
from sqlalchemy import Connection, create_engine

from agent_hud.tables import Base, PydanticJson


def render_type(kind: str, item: object, autogen_context: AutogenContext) -> str | Literal[False]:
    """Render a PydanticJson column as the Text that it stores, so that a migration does not import the app's types."""
    return "sa.Text()" if kind == "type" and isinstance(item, PydanticJson) else False


def run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection, target_metadata=Base.metadata, render_as_batch=True, render_item=render_type
    )
    with context.begin_transaction():
        context.run_migrations()


# open_database passes its connection; the alembic command line, which has none, uses the URL of alembic.ini.
match context.config.attributes.get("connection"):
    case Connection() as connection:
        run_migrations(connection)
    case None:
        with create_engine(context.config.get_main_option("sqlalchemy.url", "")).begin() as connection:
            run_migrations(connection)
    case other:
        raise TypeError(f"the alembic connection is a {type(other).__name__}, not a SQLAlchemy Connection")
