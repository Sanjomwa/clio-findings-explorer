"""Add findings.key_phrase: an optional highlighted phrase of the teaser.

NULL when there is none. Otherwise it must be non-blank and an exact substring of `teaser`, so it
adds no claim of its own. `snapshot_reader` keeps SELECT: table-level grants cover columns
added later.

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

CONSTRAINT = "ck_findings_key_phrase_in_teaser"


def upgrade() -> None:
    op.add_column("findings", sa.Column("key_phrase", sa.Text(), nullable=True))
    op.create_check_constraint(
        CONSTRAINT,
        "findings",
        "key_phrase IS NULL OR (btrim(key_phrase) <> '' AND strpos(teaser, key_phrase) > 0)",
    )


def downgrade() -> None:
    op.drop_constraint(CONSTRAINT, "findings", type_="check")
    op.drop_column("findings", "key_phrase")
