from fastapi import APIRouter

from app.api.documents import router as documents_router
from app.api.qa import router as qa_router

router = APIRouter()


@router.get("/health", tags=["health"])
async def api_health() -> dict[str, str]:
    return {"status": "ok"}


router.include_router(documents_router)
router.include_router(qa_router)
api_router = router
