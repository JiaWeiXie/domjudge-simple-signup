import pathlib

import environs
from domjudge_tool_cli.models.domserver import DomServerClient

ENV_FILE = pathlib.Path(__file__).with_name(".env")


class Settings(DomServerClient):
    google_form_id: str | None = None
    min_password_length: int | None = None
    # Set when the server reports its own minimum; see
    # BaseDomServerWeb.get_min_password_length.
    detected_min_password_length: int | None = None

    @property
    def effective_min_password_length(self) -> int:
        """Minimum password length the target DOMjudge enforces on signup.

        The server's own value is ground truth: it rejects shorter passwords
        regardless of configuration, so a lower configured value would only make
        the form advertise a policy that fails after the team and user exist. A
        configured value may therefore raise the floor but never lower it.
        Precedence: server value floors the configured value; without a server
        value the configured value applies, then a version-derived guess.
        """
        configured = (
            max(self.min_password_length, 0)
            if self.min_password_length is not None
            else None
        )
        if self.detected_min_password_length is not None:
            detected = max(self.detected_min_password_length, 0)
            return max(detected, configured or 0)
        if configured is not None:
            return configured
        return _default_min_password_length(self.version)


def _default_min_password_length(version: str) -> int:
    """Minimum user password length enforced by the DOMjudge web UI.

    DOMjudge added a 10 byte minimum in 8.0 and still ships 10 in 8.3, measured
    with PHP strlen() so multi-byte characters count once per UTF-8 byte. Older
    releases (7.x) accept any non-empty password. Unknown versions fall back to
    the 8.x minimum so an account is never created without a password.
    """
    parts = version.strip().split(".")
    try:
        major, minor = int(parts[0]), int(parts[1])
    except (IndexError, ValueError):
        return 10
    return 10 if (major, minor) >= (8, 0) else 0


def _optional_int(env: environs.Env, name: str) -> int | None:
    val = env.str(name, None)
    if val is None or not str(val).strip():
        return None
    return int(val)


def _optional_float(env: environs.Env, name: str, default: float = 60.0) -> float:
    val = env.str(name, None)
    if val is None or not str(val).strip():
        return default
    return float(val)


def _optional_bool(env: environs.Env, name: str, default: bool = False) -> bool:
    val = env.str(name, None)
    if val is None or not str(val).strip():
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _optional_str(env: environs.Env, name: str) -> str | None:
    val = env.str(name, None)
    if val is None or not str(val).strip():
        return None
    return str(val)


def _optional_list_int(env: environs.Env, name: str) -> list[int]:
    val = env.str(name, None)
    if val is None or not str(val).strip():
        return []
    return [int(x.strip()) for x in val.split(",") if x.strip()]


def load_settings(env_file: pathlib.Path = ENV_FILE) -> Settings:
    env = environs.Env()
    if env_file.exists():
        env.read_env(env_file, recurse=False)

    host = env.str("HOST")
    username = env.str("USERNAME")
    password = env.str("PASSWORD")
    disable_ssl = _optional_bool(env, "DISABLE_SSL", False)
    timeout = _optional_float(env, "TIMEOUT", 60.0)
    max_connections = _optional_int(env, "MAX_CONNECTIONS")
    max_keepalive_connections = _optional_int(env, "MAX_KEEPALIVE_CONNECTIONS")
    category_id = _optional_int(env, "CATEGORY_ID")
    affiliation_id = _optional_int(env, "AFFILIATION_ID")
    affiliation_country = _optional_str(env, "AFFILIATION_COUNTRY") or "TWN"
    user_roles = _optional_list_int(env, "USER_ROLES")
    version = env.str("VERSION")
    api_version = env.str("API_VERSION")
    google_form_id = _optional_str(env, "GOOGLEFORM_ID")
    min_password_length = _optional_int(env, "MIN_PASSWORD_LENGTH")

    return Settings(
        host=host,  # type: ignore[arg-type]
        username=username,
        password=password,
        disable_ssl=disable_ssl,
        timeout=timeout,
        max_connections=max_connections,
        max_keepalive_connections=max_keepalive_connections,
        category_id=category_id,
        affiliation_id=affiliation_id,
        affiliation_country=affiliation_country,
        user_roles=user_roles,
        version=version,
        api_version=api_version,
        google_form_id=google_form_id,
        min_password_length=min_password_length,
    )


settings = load_settings()
GOOGLEFORM_ID = settings.google_form_id
