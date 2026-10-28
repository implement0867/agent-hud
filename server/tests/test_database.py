from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Engine, inspect, text

from agent_hud.tables import Base


def test_the_migrations_make_the_tables_of_the_models(engine: Engine) -> None:
    """Assemble: a database that the migrations made.
    Act: compare it with the models.
    Assert: no difference, and each table of the models is STRICT."""
    with engine.connect() as connection:
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
        options = inspect(connection).get_table_options
        assert all(options(table)["sqlite_strict"] for table in Base.metadata.tables)


def test_each_connection_checks_foreign_keys_and_writes_ahead(engine: Engine) -> None:
    """Act: read the pragmas of a connection.
    Assert: foreign keys on, the write-ahead log, normal sync, and a 5 s wait for a lock."""
    with engine.connect() as connection:
        pragmas = [
            connection.execute(text(f"PRAGMA {name}")).scalar()
            for name in ["foreign_keys", "journal_mode", "synchronous", "busy_timeout"]
        ]
    assert pragmas == [1, "wal", 1, 5000]
