from fastapi import APIRouter

router = APIRouter()


@router.get("/health", tags=["health"])
async def api_health() -> dict[str, str]:
    return {"status": "ok"}


api_router = router
