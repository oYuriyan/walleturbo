from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: str = "development"
    base_url: str = "http://localhost:8000"
    database_url: str = "postgresql+psycopg://walleturbo:alterar@db:5432/walleturbo"
    redis_url: str = "redis://redis:6379/0"
    oidc_issuer: str = ""
    oidc_client_id: str = ""
    oidc_client_secret: str = ""
    required_acr: str = "2"

    def validate_auth(self):
        if self.app_env == "production":
            if not self.base_url.startswith(
                "https://"
            ) or not self.oidc_issuer.startswith("https://"):
                raise RuntimeError("Produção exige HTTPS e provedor OIDC")
            if not self.oidc_client_id or not self.oidc_client_secret:
                raise RuntimeError("Produção exige credenciais OIDC")


@lru_cache
def settings():
    return Settings()
