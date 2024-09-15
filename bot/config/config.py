from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_ignore_empty=True)

    API_ID: int
    API_HASH: str

    USE_TICKETS_TO_SPIN: bool = True
    MAX_USE_TICKETS_TO_SPIN: int = 100
    SLEEP_BETWEEN_FARM: list[int] = [1800, 2400]

    USE_PROXY_FROM_FILE: bool = False


settings = Settings()
