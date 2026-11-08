from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app import telemetry
from app.routers import evidence, findings, health, methodology, timeline


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """422 with loc, msg and type only: FastAPI's default also echoes `input` and `ctx`."""
    detail = [
        {"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": detail})


def create_app(database_url: str | None = None) -> FastAPI:
    """database_url defaults to $DATABASE_URL, read on the first request that needs the db."""
    app = FastAPI(title="CLIO Findings Explorer API", version="0.7.0")
    app.state.database_url = database_url
    app.state.engine = None
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    for module in (health, timeline, findings, evidence, methodology):
        app.include_router(module.router)
    telemetry.setup_from_env(app)
    return app


app = create_app()
