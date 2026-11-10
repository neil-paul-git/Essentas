from fastapi import APIRouter

from app.api.v1 import health, items, me, products, spoilage

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(me.router)
api_router.include_router(items.router)
api_router.include_router(products.router)
api_router.include_router(spoilage.router)
