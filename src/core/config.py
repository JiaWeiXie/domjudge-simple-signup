import pathlib
from typing import Any, Optional

import environs
from domjudge_tool_cli.models.domserver import DomServerClient


class Settings(DomServerClient):
    pass


env = environs.Env()
env_file = pathlib.Path(__file__).parent / ".env"

if env_file.exists():
    env.read_env()


@env.parser_for("opint")
def optional_int_parser(value: Any) -> Optional[int]:
    if not value:
        return None

    return int(value)


@env.parser_for("opstr")
def optional_str_parser(value: Any) -> Optional[str]:
    if not value:
        return None

    return str(value)


HOST = env.str("HOST")
USERNAME = env.str("USERNAME")
PASSWORD = env.str("PASSWORD")
DISABLE_SSL = env.bool("DISABLE_SSL", False)
TIMEOUT = env.float("TIMEOUT", 60.0)
MAX_CONNECTIONS = env.opint("MAX_CONNECTIONS", None)
MAX_KEEPALIVE_CONNECTIONS = env.opint("MAX_KEEPALIVE_CONNECTIONS", None)
CATEGORY_ID = env.opint("CATEGORY_ID", None)
AFFILIATION_ID = env.opint("AFFILIATION_ID", None)
AFFILIATION_COUNTRY = env.str("AFFILIATION_COUNTRY", "TWN")
USER_ROLES = env.list("USER_ROLES", [], subcast=int)
VERSION = env.str("VERSION")
API_VERSION = env.str("API_VERSION")
GOOGLEFORM_ID = env.opstr("GOOGLEFORM_ID", None)

settings = Settings(
    host=HOST,
    username=USERNAME,
    password=PASSWORD,
    disable_ssl=DISABLE_SSL,
    timeout=TIMEOUT,
    max_connections=MAX_CONNECTIONS,
    max_keepalive_connections=MAX_KEEPALIVE_CONNECTIONS,
    category_id=CATEGORY_ID,
    affiliation_id=AFFILIATION_ID,
    affiliation_country=AFFILIATION_COUNTRY,
    user_roles=USER_ROLES,
    version=VERSION,
    api_version=API_VERSION,
)
