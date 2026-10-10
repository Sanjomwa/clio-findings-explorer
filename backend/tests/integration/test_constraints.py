import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

WEEK = {"iso2": "KE", "week": "2024-06-22"}

INSERT_FINDING = text(
    "INSERT INTO findings (slug, iso2, week_start_date, title, teaser, summary_md, published_at, position) "
    "VALUES (:slug, 'KE', '2024-06-22', 't', 't', 's', now(), :pos)"
)
INSERT_CAVEAT = text(
    "INSERT INTO finding_caveats (finding_slug, position, severity, caveat_md) "
    "VALUES (:slug, :pos, 'limitation', 'c')"
)


def count(engine, sql, **params):
    with engine.connect() as conn:
        return conn.execute(text(sql), params).scalar_one()


def test_finding_without_caveat_fails_at_commit(seeded_engine):
    with pytest.raises(DBAPIError, match="must have at least one caveat"):
        with seeded_engine.begin() as conn:
            conn.execute(INSERT_FINDING, {"slug": "no-caveat", "pos": 1})
    assert count(seeded_engine, "SELECT count(*) FROM findings") == 0


def test_finding_with_caveat_succeeds_in_either_order(seeded_engine):
    with seeded_engine.begin() as conn:
        conn.execute(INSERT_FINDING, {"slug": "with-caveat", "pos": 1})
        conn.execute(INSERT_CAVEAT, {"slug": "with-caveat", "pos": 1})
    assert count(seeded_engine, "SELECT count(*) FROM findings") == 1


def test_deleting_last_caveat_fails(seeded_engine):
    with seeded_engine.begin() as conn:
        conn.execute(INSERT_FINDING, {"slug": "one-caveat", "pos": 1})
        conn.execute(INSERT_CAVEAT, {"slug": "one-caveat", "pos": 1})
    with pytest.raises(DBAPIError, match="must have at least one caveat"):
        with seeded_engine.begin() as conn:
            conn.execute(text("DELETE FROM finding_caveats WHERE finding_slug = 'one-caveat'"))
    assert count(seeded_engine, "SELECT count(*) FROM finding_caveats") == 1


def test_deleting_one_of_two_caveats_succeeds(seeded_engine):
    with seeded_engine.begin() as conn:
        conn.execute(INSERT_FINDING, {"slug": "two-caveats", "pos": 1})
        conn.execute(INSERT_CAVEAT, {"slug": "two-caveats", "pos": 1})
        conn.execute(INSERT_CAVEAT, {"slug": "two-caveats", "pos": 2})
    with seeded_engine.begin() as conn:
        conn.execute(text("DELETE FROM finding_caveats WHERE position = 2"))
    assert count(seeded_engine, "SELECT count(*) FROM finding_caveats") == 1


def test_moving_last_caveat_to_another_finding_fails(seeded_engine):
    with seeded_engine.begin() as conn:
        for slug, pos in (("first", 1), ("second", 2)):
            conn.execute(INSERT_FINDING, {"slug": slug, "pos": pos})
            conn.execute(INSERT_CAVEAT, {"slug": slug, "pos": 1})
        conn.execute(INSERT_CAVEAT, {"slug": "second", "pos": 2})
    with pytest.raises(DBAPIError, match="must have at least one caveat"):
        with seeded_engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE finding_caveats SET finding_slug = 'second', position = 3 "
                    "WHERE finding_slug = 'first'"
                )
            )


def test_deleting_the_finding_succeeds(seeded_engine):
    with seeded_engine.begin() as conn:
        conn.execute(INSERT_FINDING, {"slug": "to-delete", "pos": 1})
        conn.execute(INSERT_CAVEAT, {"slug": "to-delete", "pos": 1})
    with seeded_engine.begin() as conn:
        conn.execute(text("DELETE FROM findings WHERE slug = 'to-delete'"))
    assert count(seeded_engine, "SELECT count(*) FROM findings") == 0
    assert count(seeded_engine, "SELECT count(*) FROM finding_caveats") == 0


def test_bad_slug_rejected(seeded_engine):
    with pytest.raises(IntegrityError), seeded_engine.begin() as conn:
        conn.execute(INSERT_FINDING, {"slug": "Bad_Slug", "pos": 1})


def test_blank_caveat_and_bad_severity_rejected(seeded_engine):
    with seeded_engine.begin() as conn:
        conn.execute(INSERT_FINDING, {"slug": "checks", "pos": 1})
        conn.execute(INSERT_CAVEAT, {"slug": "checks", "pos": 1})
    for sql in (
        "INSERT INTO finding_caveats (finding_slug, position, severity, caveat_md) VALUES ('checks', 2, 'limitation', '  ')",
        "INSERT INTO finding_caveats (finding_slug, position, severity, caveat_md) VALUES ('checks', 2, 'warning', 'x')",
    ):
        with pytest.raises(IntegrityError), seeded_engine.begin() as conn:
            conn.execute(text(sql))


def test_finding_must_reference_a_real_week(seeded_engine):
    with pytest.raises(IntegrityError):
        with seeded_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO findings (slug, iso2, week_start_date, title, teaser, summary_md, published_at, position) "
                    "VALUES ('bad-week', 'KE', '1900-01-06', 't', 't', 's', now(), 1)"
                )
            )
            conn.execute(INSERT_CAVEAT, {"slug": "bad-week", "pos": 1})


def test_bad_primary_regime_rejected_by_check(seeded_engine):
    with pytest.raises(IntegrityError, match="ck_regime_weeks_primary_regime"):
        with seeded_engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE regime_weeks SET primary_regime = 'NOT_A_REGIME' "
                    "WHERE week_start_date = '2024-06-22'"
                )
            )
