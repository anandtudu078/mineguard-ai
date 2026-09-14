"""Application settings, loaded from the environment (see /.env.example)."""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the compliance API."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Core ---
    api_env: str = "development"
    api_secret_key: str = "change-me-in-production"
    api_cors_origins: list[str] = ["http://localhost:3000"]

    # --- Datastore ---
    # Port 5434 matches infra/docker-compose.yml, which avoids the very common
    # clash with a pre-existing local PostgreSQL on 5432.
    database_url: str = "postgresql+psycopg://mining:mining@localhost:5434/mining_governance"
    database_echo: bool = False

    # --- Authentication ---
    #: ``supabase`` verifies Supabase Auth JWTs. ``disabled`` skips verification
    #: entirely and treats every request as a development administrator.
    #: Startup refuses to run with ``disabled`` when api_env is "production".
    auth_mode: str = "disabled"

    #: Supabase project URL, e.g. https://abcdefgh.supabase.co
    supabase_url: str | None = None
    #: Legacy shared HS256 secret (Project Settings -> API -> JWT Secret).
    #: Ignored when the project signs asymmetrically, which newer projects do.
    supabase_jwt_secret: str | None = None
    #: Service-role key for admin calls such as sending invites. Bypasses RLS;
    #: server-only, never exposed to the browser.
    supabase_service_role_key: str | None = None
    #: Expected ``aud`` claim. Supabase issues "authenticated" for signed-in users.
    supabase_jwt_audience: str = "authenticated"
    #: Expected ``iss`` claim. Defaults to ``{supabase_url}/auth/v1``.
    supabase_jwt_issuer: str | None = None
    #: The role granted to the very first user to sign in, when no profiles
    #: exist yet. Every later unknown user is rejected unless self-registration
    #: is on.
    bootstrap_role: str = "admin"
    #: When true, a Supabase-authenticated user with no profile is provisioned
    #: automatically with ``self_registration_role`` instead of being refused.
    #: Pairs with "Allow new users to sign up" in the Supabase dashboard.
    self_registration_enabled: bool = False
    #: The role handed to self-registered users. Kept low-privilege by default:
    #: inspectors read the register; they cannot manage users or reference data.
    self_registration_role: str = "inspector"

    #: Where Supabase sends a person after they accept an invite, so they can
    #: set their password. Must also be listed under Authentication -> URL
    #: Configuration -> Redirect URLs in the Supabase dashboard.
    invite_redirect_url: str = "http://localhost:3000/auth/callback"

    # --- Background jobs ---
    redis_url: str = "redis://localhost:6379/0"

    # --- Resend reminder delivery ---
    resend_api_key: str | None = None
    resend_from_email: str | None = None
    resend_from_name: str = "MineGuard compliance"
    reminder_send_enabled: bool = False

    # --- Document storage ---
    document_storage_path: str = "./storage/uploads"
    #: When true (and Supabase credentials exist), uploads go to Supabase
    #: Storage instead of local disk. Cloud containers have ephemeral disks,
    #: so production deployments must enable this.
    supabase_storage_enabled: bool = False

    # --- LLM providers (used from Feature 2 onward) ---
    gemini_api_key: str | None = None
    groq_api_key: str | None = None

    # --- Compliance policy defaults ---
    #: A licence expiring within this many days is flagged as "expiring soon".
    licence_expiry_warning_days: int = 90

    @field_validator("api_cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Allow a comma-separated string in CORS_ORIGINS environment variables."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("supabase_url", "supabase_jwt_secret", "supabase_jwt_issuer", mode="before")
    @classmethod
    def _sanitize_string_settings(cls, value: object) -> object:
        """Strip whitespace and coerce empty strings to None."""
        if isinstance(value, str):
            trimmed = value.strip()
            return trimmed if trimmed else None
        return value

    @property
    def is_test(self) -> bool:
        return self.api_env == "test"

    @property
    def is_production(self) -> bool:
        return self.api_env == "production"

    @property
    def jwks_url(self) -> str | None:
        """Supabase's public signing keys, for projects using asymmetric JWTs."""
        if not self.supabase_url:
            return None
        return f"{self.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"

    @property
    def resolved_issuers(self) -> list[str] | None:
        """The accepted ``iss`` claims.

        Supabase tokens carry either the full project auth URL (for modern JWKS-signed
        tokens) or the literal string ``"supabase"`` (for HS256 tokens). Accepting
        both prevents unexpected issuer rejection across token formats.
        """
        if self.supabase_jwt_issuer:
            return [self.supabase_jwt_issuer]
        if not self.supabase_url:
            return None
        url_issuer = f"{self.supabase_url.rstrip('/')}/auth/v1"
        return [url_issuer, "supabase"]

    @property
    def resolved_issuer(self) -> str | None:
        """The primary ``iss`` claim, implied by ``supabase_url`` if unset."""
        if self.supabase_jwt_issuer:
            return self.supabase_jwt_issuer
        if not self.supabase_url:
            return None
        return f"{self.supabase_url.rstrip('/')}/auth/v1"

    @property
    def auth_enabled(self) -> bool:
        return self.auth_mode == "supabase"

    @property
    def auth_configured(self) -> bool:
        """Whether there is anything to verify a token *with*.

        Verified at startup rather than per-request so a half-configured
        deployment fails immediately and loudly instead of rejecting every
        login with an opaque 401.
        """
        return bool(self.supabase_jwt_secret or self.supabase_url)

    @field_validator("auth_mode")
    @classmethod
    def _validate_auth_mode(cls, value: str) -> str:
        allowed = {"disabled", "supabase"}
        if value not in allowed:
            raise ValueError(f"auth_mode must be one of {sorted(allowed)}, got {value!r}")
        return value


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    return Settings()


settings = get_settings()
