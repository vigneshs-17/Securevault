import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, select, text

from app.db.base import Base
from app.db.database import engine
from app.db.migrate import BASELINE, adopt_existing_database, migration_config, upgrade_database


def snapshot():
    with engine.connect() as connection:
        return {table.name: list(connection.execute(select(table).order_by(table.c.id)))
                for table in Base.metadata.sorted_tables}


def remove_tracking():
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE alembic_version"))


def test_migrated_schema_matches_models():
    with engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True, "compare_server_default": True})
        assert compare_metadata(context, Base.metadata) == []
        assert context.get_current_revision() == "0002_vault_metadata"
        for table in Base.metadata.sorted_tables:
            assert inspect(connection).get_pk_constraint(table.name)["constrained_columns"] == [c.name for c in table.primary_key]


def test_upgrade_again_preserves_rows(access_token):
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as client:
        response = client.post("/vault/items", headers={"Authorization": "Bearer " + access_token},
                               json={"title": "Migration preservation", "password": "SyntheticSecret123!"})
        assert response.status_code == 201
    before = snapshot()
    upgrade_database(engine)
    assert snapshot() == before


def test_adopt_existing_preserves_rows(access_token):
    with engine.begin() as connection:
        config = migration_config()
        config.attributes["connection"] = connection
        command.downgrade(config, BASELINE)
    with engine.connect() as connection:
        before = list(connection.execute(text("SELECT id, email, hashed_password FROM users ORDER BY id")))
    remove_tracking()
    adopt_existing_database(engine)
    with engine.connect() as connection:
        assert list(connection.execute(text("SELECT id, email, hashed_password FROM users ORDER BY id"))) == before
    with engine.connect() as connection:
        assert MigrationContext.configure(connection).get_current_revision() == BASELINE
    upgrade_database(engine)


def test_adoption_rejects_schema_drift():
    remove_tracking()
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE users ADD COLUMN unexpected_column TEXT"))
    with pytest.raises(RuntimeError, match="adoption refused"):
        adopt_existing_database(engine)
    assert "alembic_version" not in inspect(engine).get_table_names()


def test_adoption_rejects_already_versioned_database():
    with pytest.raises(RuntimeError, match="already has migration tracking"):
        adopt_existing_database(engine)


def test_downgrade_and_fresh_upgrade_in_disposable_database():
    config = migration_config()
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "base")
    assert set(inspect(engine).get_table_names()) == {"alembic_version"}
    upgrade_database(engine)
    test_migrated_schema_matches_models()
