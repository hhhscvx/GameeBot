from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_ignore_empty=True)

    API_ID: int
    API_HASH: str

    REF_CODE: str = 'ref_1051277129'
    USE_TICKETS_TO_SPIN: bool = True
    MAX_USE_TICKETS_TO_SPIN: int = 100


settings = Settings()
