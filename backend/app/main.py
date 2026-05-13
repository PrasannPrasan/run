from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.settings import settings
from app.db.session import engine
from app.db.models import Base
from app.api.router import api_router


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)

    cors_list = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_list or ["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.get("/", include_in_schema=False)
    def root():
        return RedirectResponse(settings.frontend_url)

    @app.on_event("startup")
    def _startup():
        Base.metadata.create_all(bind=engine)

    app.include_router(api_router)

    return app


app = create_app()
