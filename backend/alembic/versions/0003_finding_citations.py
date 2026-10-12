"""Add findings.citations: public sources for a finding's real-world event statements.

A JSONB array of {claim, citation, url} objects in display order; the seed validates the items.
`snapshot_reader` keeps SELECT: table-level grants cover columns added later.

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "findings",
        sa.Column(
            "citations",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("findings", "citations")
