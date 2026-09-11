from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    ai_api_key: str = ""
    frontend_url: str = "http://localhost:3000"

    # Extra origins CORS should also allow, comma-separated (e.g. a preview
    # deployment domain alongside the primary production frontend_url).
    # Optional -- unset behaves exactly as before, a single allowed origin.
    additional_cors_origins: str = ""

    @property
    def cors_origins(self) -> list[str]:
        extra = [origin.strip() for origin in self.additional_cors_origins.split(",") if origin.strip()]
        return [self.frontend_url, *extra]


settings = Settings()
