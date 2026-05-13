from fastapi import APIRouter

from app.api.routes import auth
from app.api.routes import enrich
from app.api.routes import webhooks


api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(enrich.router, prefix="/enrich", tags=["enrich"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])

