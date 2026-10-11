"""Read-only, no-login role for the MCP `query_snapshot` tool.

The local Postgres user is a superuser in the official image, so a read-only transaction alone
would still allow server-file functions such as pg_read_file(). The tool runs
`SET LOCAL ROLE snapshot_reader` before the query; this role holds SELECT on the public tables
and nothing else.

`alembic_version` is readable: the blanket SELECT grant covers it, it holds only a revision id.

Roles are cluster-wide, so the role is created only if missing, and the downgrade drops it only
when no other database on the server still depends on it.

Revision ID: 0002
Revises: 0001
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'snapshot_reader') THEN
                CREATE ROLE snapshot_reader
                    NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
            END IF;
        END
        $$
        """
    )
    op.execute("GRANT USAGE ON SCHEMA public TO snapshot_reader")
    op.execute("GRANT SELECT ON ALL TABLES IN SCHEMA public TO snapshot_reader")
    # Tables created later by the role that runs migrations are readable too.
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO snapshot_reader"
    )


def downgrade() -> None:
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE SELECT ON TABLES FROM snapshot_reader"
    )
    op.execute("REVOKE SELECT ON ALL TABLES IN SCHEMA public FROM snapshot_reader")
    op.execute("REVOKE USAGE ON SCHEMA public FROM snapshot_reader")
    # DROP ROLE fails while another database on the server still grants it privileges.
    op.execute(
        """
        DO $$
        BEGIN
            DROP ROLE IF EXISTS snapshot_reader;
        EXCEPTION WHEN dependent_objects_still_exist THEN
            RAISE NOTICE 'snapshot_reader kept: other databases on this server still use it';
        END
        $$
        """
    )
