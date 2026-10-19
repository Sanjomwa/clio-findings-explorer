from fastapi import FastAPI

from app import telemetry
from app.routers import evidence, findings, health, methodology, timeline


def create_app(database_url: str | None = None) -> FastAPI:
    """database_url defaults to $DATABASE_URL, read on the first request that needs the db."""
    app = FastAPI(title="CLIO Findings Explorer API", version="0.7.0")
    app.state.database_url = database_url
    app.state.engine = None
    for module in (health, timeline, findings, evidence, methodology):
        app.include_router(module.router)
    telemetry.setup_from_env(app)
    return app


app = create_app()
