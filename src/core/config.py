import pathlib

import environs
from domjudge_tool_cli.models.domserver import DomServerClient

ENV_FILE = pathlib.Path(__file__).with_name(".env")


class Settings(DomServerClient):
    google_form_id: str | None = None


def _optional_int(env: environs.Env, name: str) -> int | None:
    val = env.str(name, None)
    if val is None or not str(val).strip():
        return None
    return int(val)


def _optional_str(env: environs.Env, name: str) -> str | None:
    val = env.str(name, None)
    if val is None or not str(val).strip():
        return None
    return str(val)


def load_settings(env_file: pathlib.Path = ENV_FILE) -> Settings:
    env = environs.Env()
    if env_file.exists():
        env.read_env(env_file, recurse=False)

    host = env.str("HOST")
    username = env.str("USERNAME")
    password = env.str("PASSWORD")
    disable_ssl = env.bool("DISABLE_SSL", False)
    timeout = env.float("TIMEOUT", 60.0)
    max_connections = _optional_int(env, "MAX_CONNECTIONS")
    max_keepalive_connections = _optional_int(env, "MAX_KEEPALIVE_CONNECTIONS")
    category_id = _optional_int(env, "CATEGORY_ID")
    affiliation_id = _optional_int(env, "AFFILIATION_ID")
    affiliation_country = env.str("AFFILIATION_COUNTRY", "TWN")
    user_roles = env.list("USER_ROLES", [], subcast=int)
    version = env.str("VERSION")
    api_version = env.str("API_VERSION")
    google_form_id = _optional_str(env, "GOOGLEFORM_ID")

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
    )


settings = load_settings()
GOOGLEFORM_ID = settings.google_form_id
