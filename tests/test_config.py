from pathlib import Path

import environs
import pytest
from pydantic import ValidationError

from core.config import load_settings


def test_load_settings_all_valid_keys(tmp_path: Path) -> None:
    env_content = """HOST=https://domjudge.example.test
USERNAME=admin_user
PASSWORD=admin_password
DISABLE_SSL=True
TIMEOUT=45.5
MAX_CONNECTIONS=15
MAX_KEEPALIVE_CONNECTIONS=8
CATEGORY_ID=3
AFFILIATION_ID=5
AFFILIATION_COUNTRY=TWN
USER_ROLES=3,4
VERSION=7.3.2
API_VERSION=v4
GOOGLEFORM_ID=1FAIpQLSc_EXAMPLE
"""
    env_file = tmp_path / ".env"
    env_file.write_text(env_content, encoding="utf-8")

    s = load_settings(env_file)
    assert str(s.host) == "https://domjudge.example.test/"
    assert s.username == "admin_user"
    assert s.password == "admin_password"
    assert s.disable_ssl is True
    assert s.timeout == 45.5
    assert s.max_connections == 15
    assert s.max_keepalive_connections == 8
    assert s.category_id == 3
    assert s.affiliation_id == 5
    assert s.affiliation_country == "TWN"
    assert s.user_roles == [3, 4]
    assert s.version == "7.3.2"
    assert s.api_version == "v4"
    assert s.google_form_id == "1FAIpQLSc_EXAMPLE"


def test_load_settings_blank_optional_keys(tmp_path: Path) -> None:
    env_content = """HOST=https://domjudge.example.test
USERNAME=admin_user
PASSWORD=admin_password
DISABLE_SSL=False
TIMEOUT=
MAX_CONNECTIONS=
MAX_KEEPALIVE_CONNECTIONS=
CATEGORY_ID=
AFFILIATION_ID=
AFFILIATION_COUNTRY=
USER_ROLES=
VERSION=8.1.3
API_VERSION=v4
GOOGLEFORM_ID=
"""
    env_file = tmp_path / ".env"
    env_file.write_text(env_content, encoding="utf-8")

    s = load_settings(env_file)
    assert s.disable_ssl is False
    assert s.timeout == 60.0
    assert s.affiliation_country == "TWN"
    assert s.max_connections is None
    assert s.max_keepalive_connections is None
    assert s.category_id is None
    assert s.affiliation_id is None
    assert s.google_form_id is None
    assert s.user_roles == []


def test_load_settings_os_env_precedence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        """HOST=https://file.example.test
USERNAME=file_user
PASSWORD=file_pass
VERSION=7.3.2
API_VERSION=v4
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("HOST", "https://env.example.test")
    monkeypatch.setenv("USERNAME", "env_user")
    monkeypatch.setenv("PASSWORD", "env_pass")
    monkeypatch.setenv("VERSION", "8.1.3")
    monkeypatch.setenv("API_VERSION", "v4")

    s = load_settings(env_file)
    assert str(s.host) == "https://env.example.test/"
    assert s.username == "env_user"
    assert s.password == "env_pass"
    assert s.version == "8.1.3"


def test_load_settings_missing_required_keys(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("HOST=https://example.test\n", encoding="utf-8")

    with pytest.raises((environs.EnvError, ValidationError)):
        load_settings(env_file)


@pytest.mark.parametrize(
    "missing_key", ["HOST", "USERNAME", "PASSWORD", "VERSION", "API_VERSION"]
)
def test_load_settings_each_required_key_is_required(
    tmp_path: Path,
    missing_key: str,
) -> None:
    values = {
        "HOST": "https://example.test",
        "USERNAME": "user",
        "PASSWORD": "password",
        "VERSION": "7.3.2",
        "API_VERSION": "v4",
    }
    values.pop(missing_key)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(f"{key}={value}" for key, value in values.items()),
        encoding="utf-8",
    )

    with pytest.raises((environs.EnvError, ValidationError)):
        load_settings(env_file)
