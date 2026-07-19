from loguru import logger

from config import settings

logger.remove()

logger.add(
    sink=lambda msg: print(msg, end=""),
    level=settings.LOG_LEVEL,
    colorize=True,
)

__all__ = ["logger"]