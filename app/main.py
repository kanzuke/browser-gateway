from contextlib import asynccontextmanager

from fastapi import FastAPI

from browser import browser
from routes.health import router as health_router


@asynccontextmanager
async def lifespan(app: FastAPI):

    await browser.start()

    yield

    await browser.stop()


app = FastAPI(
    title="Hermes Browser Gateway",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(health_router)