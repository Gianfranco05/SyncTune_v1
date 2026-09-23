from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Spotify (required)
    spotify_client_id: str
    spotify_client_secret: str
    spotify_redirect_uri: str

    # YouTube Data API v3 (required) — API key, used for public video/
    # playlist metadata lookups that don't need a signed-in user.
    youtube_api_key: str

    # Signs the session cookie AND derives the Fernet key that encrypts
    # OAuth tokens at rest (see core/crypto.py). Keep this secret.
    secret_key: str

    # Frontend origin, for CORS and post-login redirect.
    frontend_origin: str

    # PostgreSQL, psycopg2 driver, e.g.:
    # postgresql+psycopg2://synctune:synctune@localhost:5434/synctune
    database_url: str

    # Google OAuth (FASE 5) — optional: only "Conectar YouTube" needs these.
    # Everything else (Spotify, video/playlist lookups via youtube_api_key)
    # works fine if they're left unset.
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str | None = None


settings = Settings()
