from fastapi import APIRouter

from browser import browser

router = APIRouter()


@router.get("/health")
async def health():

    return {
        "status": "ok",
        "browser": (
            "running"
            if browser.started
            else "not_started"
        ),
    }