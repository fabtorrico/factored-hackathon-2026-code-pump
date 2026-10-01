from fastapi import FastAPI

from app.api.errors import banking_error_handler
from app.api.routes import router
from app.banking.errors import BankingError
from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name)
    # One place translates a domain reason into HTTP, so no route can leak an internal message,
    # a SQL fragment or a filesystem path.
    app.add_exception_handler(BankingError, banking_error_handler)
    app.include_router(router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
