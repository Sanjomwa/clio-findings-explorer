import os

from sqlalchemy import Engine, create_engine


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set (expected postgresql+psycopg://...)")
    return url


def make_engine(url: str | None = None) -> Engine:
    return create_engine(url or database_url())
