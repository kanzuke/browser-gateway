from pydantic_settings import BaseSettings


class Settings(BaseSettings):

    PROFILE_PATH: str = "/profiles/default"

    DOWNLOAD_PATH: str = "/downloads"

    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"


settings = Settings()