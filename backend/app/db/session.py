import os

from sqlalchemy import Engine, create_engine


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set (expected postgresql+psycopg://...)")
    return url


def make_engine(url: str | None = None) -> Engine:
    return create_engine(url or database_url())


def make_api_engine(url: str | None = None) -> Engine:
    """Engine for the API: short connect timeout so /api/health answers quickly when db is down."""
    return create_engine(
        url or database_url(), connect_args={"connect_timeout": 5}, pool_pre_ping=True
    )
