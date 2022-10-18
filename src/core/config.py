import pathlib

import environs
from domjudge_tool_cli.models.domserver import DomServerClient


class Settings(DomServerClient):
    pass


env = environs.Env()
env_file = pathlib.Path(__file__).parent / ".env"

if env_file.exists():
    env.read_env()

HOST = env.str("HOST")
USERNAME = env.str("USERNAME")
PASSWORD = env.str("PASSWORD")
DISABLE_SSL = env.bool("DISABLE_SSL", default=False)
TIMEOUT = env.float("TIMEOUT", 60.0)
MAX_CONNECTIONS = env.int("MAX_CONNECTIONS", default=None)
MAX_KEEPALIVE_CONNECTIONS = env.int("MAX_KEEPALIVE_CONNECTIONS", default=None)
CATEGORY_ID = env.int("CATEGORY_ID", default=None)
AFFILIATION_ID = env.int("AFFILIATION_ID", default=None)
AFFILIATION_COUNTRY = env.str("AFFILIATION_COUNTRY", default="TWN")
USER_ROLES = env.list("AFFILIATION_COUNTRY", default=None)
VERSION = env.str("VERSION")
API_VERSION = env.str("API_VERSION")

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
