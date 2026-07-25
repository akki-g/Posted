from fastapi import APIRouter

from app.api.routes import (
    assistant,
    auth,
    connections,
    feed,
    health,
    market,
    money,
    plaid,
    portfolio,
    settings,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(health.router)
api_router.include_router(portfolio.router)
api_router.include_router(feed.router)
api_router.include_router(connections.router)
api_router.include_router(settings.router)
api_router.include_router(money.router)
api_router.include_router(plaid.router)
api_router.include_router(assistant.router)
api_router.include_router(market.router)
