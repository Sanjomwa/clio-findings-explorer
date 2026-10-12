from sqlalchemy import inspect, text

from alembic import command
from tests.integration.conftest import alembic_config

EXPECTED = {
    "regime_weeks", "acled_signal_context", "ooni_weekly_signals",
    "google_transparency_requests", "snapshot_meta", "snapshot_tables",
    "findings", "finding_caveats",
}  # fmt: skip


def tables(engine):
    return set(inspect(engine).get_table_names()) - {"alembic_version"}


def test_upgrade_downgrade_upgrade(empty_engine):
    config = alembic_config(empty_engine)
    command.upgrade(config, "head")
    assert tables(empty_engine) == EXPECTED
    command.downgrade(config, "base")
    assert tables(empty_engine) == set()
    with empty_engine.connect() as conn:
        left = conn.execute(
            text("SELECT count(*) FROM pg_proc WHERE proname = 'enforce_finding_has_caveat'")
        ).scalar_one()
    assert left == 0
    command.upgrade(config, "head")
    assert tables(empty_engine) == EXPECTED


def test_snapshot_meta_allows_only_one_row(migrated_engine):
    import pytest
    from sqlalchemy.exc import IntegrityError

    insert = text(
        "INSERT INTO snapshot_meta (version, exported_at, acled_access_date, manifest) "
        "VALUES (:v, now(), '2026-03-26', '{}')"
    )
    with migrated_engine.begin() as conn:
        conn.execute(insert, {"v": "a"})
    with pytest.raises(IntegrityError), migrated_engine.begin() as conn:
        conn.execute(insert, {"v": "b"})


def _grants(engine):
    with engine.connect() as conn:
        return conn.execute(
            text(
                "SELECT count(*) FROM information_schema.role_table_grants "
                "WHERE grantee = 'snapshot_reader'"
            )
        ).scalar_one()


def test_snapshot_reader_role(seeded_engine):
    import pytest
    from sqlalchemy.exc import DBAPIError

    with seeded_engine.connect() as conn:
        role = conn.execute(
            text(
                "SELECT rolcanlogin, rolsuper, rolcreatedb, rolcreaterole, rolinherit "
                "FROM pg_roles WHERE rolname = 'snapshot_reader'"
            )
        ).one()
    assert tuple(role) == (False, False, False, False, False)

    def as_reader(sql):
        with seeded_engine.connect() as conn:
            conn.execute(text("SET TRANSACTION READ WRITE"))
            conn.execute(text("SET LOCAL ROLE snapshot_reader"))
            try:
                return conn.execute(text(sql)).all()
            finally:
                conn.rollback()

    assert as_reader("SELECT count(*) FROM regime_weeks")[0][0] == 1523
    assert as_reader("SELECT count(*) FROM alembic_version")[0][0] == 1
    with pytest.raises(DBAPIError, match="permission denied"):
        as_reader("INSERT INTO snapshot_meta SELECT * FROM snapshot_meta")
    with pytest.raises(DBAPIError, match="permission denied"):
        as_reader("SELECT pg_read_file('PG_VERSION')")


def test_snapshot_reader_migration_downgrade_revokes_and_upgrade_restores(migrated_engine):
    config = alembic_config(migrated_engine)
    assert _grants(migrated_engine) > 0
    command.downgrade(config, "0001")
    # The role itself may remain (roles are cluster-wide and the dev database still uses it);
    # in this database it holds nothing.
    assert _grants(migrated_engine) == 0
    command.upgrade(config, "head")
    assert _grants(migrated_engine) > 0


def test_finding_citations_column_defaults_to_empty_and_downgrade_drops_it(migrated_engine):
    config = alembic_config(migrated_engine)

    def columns():
        with migrated_engine.connect() as conn:
            return conn.execute(
                text(
                    "SELECT column_name, is_nullable, column_default FROM information_schema.columns "
                    "WHERE table_name = 'findings' AND column_name = 'citations'"
                )
            ).all()

    (name, nullable, default), = columns()
    assert (nullable, "'[]'::jsonb" in default) == ("NO", True)
    command.downgrade(config, "0002")
    assert columns() == []
    command.upgrade(config, "head")
    assert len(columns()) == 1
