from fastapi import APIRouter, FastAPI
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.errors import AppError, app_error_handler, http_error_handler
from app.routers import (
    accounts,
    auth,
    businesses,
    catalog,
    dashboard,
    health,
    insights,
    inventory,
    onboarding,
    purchase_orders,
    sales,
)
from app.routers import settings as settings_router

app = FastAPI(title="Inventory API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(HTTPException, http_error_handler)

app.include_router(health.router)

api_v1 = APIRouter(prefix="/api/v1")
api_v1.include_router(auth.router)
api_v1.include_router(businesses.router)
api_v1.include_router(catalog.router)
api_v1.include_router(inventory.router)
api_v1.include_router(purchase_orders.router)
api_v1.include_router(dashboard.router)
api_v1.include_router(insights.router)
api_v1.include_router(accounts.router)
api_v1.include_router(settings_router.router)
api_v1.include_router(sales.router)
api_v1.include_router(onboarding.router)
app.include_router(api_v1)
