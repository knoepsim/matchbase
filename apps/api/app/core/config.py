from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""

    # Database
    database_url: str = "postgresql+asyncpg://localhost:5432/beerpong"

    # JWT
    secret_key: str = "CHANGE-ME-IN-PRODUCTION"
    # The access token is short-lived and renewed in the background; what keeps somebody logged in is the refresh
    # token: every use of it issues a new one for another refresh_token_expire_days, so an active user stays logged in
    # and a phone that was in a pocket for an hour just renews silently.
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    # Session cookies (HttpOnly, SameSite=Lax). Secure by default in production only: a phone that opens the dev
    # server over plain http in the local network would not get a Secure cookie. Set COOKIE_SECURE to override.
    cookie_secure: bool | None = None
    # Path the browser sees for the refresh endpoint (the web app proxies the API under /api)
    refresh_cookie_path: str = "/api/auth"

    # SMS Verification
    sms_code_expire_minutes: int = 5
    sms_code_length: int = 6

    # Abuse protection for SMS codes
    sms_resend_cooldown_seconds: int = 60
    sms_max_requests_per_hour: int = 5
    sms_max_verify_attempts: int = 5

    # Browser origins that may call the API directly (comma separated). Outside production, any http(s) origin is
    # allowed on top of this, so a phone in the same network works without configuration.
    cors_origins: str = "http://localhost:3000"

    # Server-Sent Events (live view): heartbeat keeps proxies from closing an idle stream, a stream is closed after
    # sse_max_seconds (the browser reconnects, which checks access again), at most sse_max_connections at once
    sse_heartbeat_seconds: float = 20
    sse_max_seconds: float = 600
    sse_max_connections: int = 500

    # Release version (APP_VERSION): the image gets it from the git tag at build time, see docs/CONTRIBUTING.md
    app_version: str = "0.0.0-dev"

    # Edge: the same API runs in the cloud and on a Tournament Core at the venue (docs/edge). Only the core listens to
    # the table controllers: MQTT_URL (mqtt://host:1883) switches the listener on, without it nothing changes.
    node_role: Literal["cloud", "edge"] = "cloud"
    node_name: str = "MatchBase"
    mqtt_url: str | None = None
    mqtt_topic_prefix: str = "tables"
    # a table controller sends its state on every change and as a heartbeat; silent longer than this, it is offline
    sensor_offline_seconds: float = 30

    # Set ENVIRONMENT=production to refuse insecure defaults (dummy SMS, default secret key)
    environment: str = "development"

    # SMS Backend: "dummy" (v1) or "httpsms" (future)
    sms_backend: str = "dummy"

    # System Admin
    super_admin_phones: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


    @model_validator(mode="after")
    def _reject_insecure_production_config(self) -> "Settings":
        if self.environment != "production":
            return self
        problems = []
        if self.sms_backend == "dummy":
            problems.append("SMS_BACKEND must not be 'dummy' (fixed code 123456, codes are logged)")
        if self.secret_key == "CHANGE-ME-IN-PRODUCTION":
            problems.append("SECRET_KEY must be changed")
        if problems:
            raise ValueError("Insecure production configuration: " + "; ".join(problems))
        return self


    @property
    def cookies_secure(self) -> bool:
        return self.environment == "production" if self.cookie_secure is None else self.cookie_secure


settings = Settings()
