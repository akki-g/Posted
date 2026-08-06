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
    plaid_investments,
    portfolio,
    settings,
    sms_link,
    telnyx,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(health.router)
api_router.include_router(portfolio.router)
api_router.include_router(feed.router)
api_router.include_router(connections.router)
api_router.include_router(settings.router)
api_router.include_router(sms_link.router)
api_router.include_router(money.router)
api_router.include_router(plaid.router)
api_router.include_router(plaid_investments.router)
api_router.include_router(assistant.router)
api_router.include_router(market.router)
api_router.include_router(telnyx.router)
