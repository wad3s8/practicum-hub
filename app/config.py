from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    jwt_secret: SecretStr = Field(min_length=32)
    access_token_expire_minutes: int = Field(default=60, ge=1, le=1440)

    @field_validator("jwt_secret")
    @classmethod
    def reject_placeholder(cls, value: SecretStr) -> SecretStr:
        if value.get_secret_value().startswith("replace-with"):
            raise ValueError("Generate a random JWT_SECRET before starting the application")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
