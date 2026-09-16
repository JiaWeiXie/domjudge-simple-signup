from pathlib import Path

import environs
import pytest
from pydantic import ValidationError

from core.config import Settings, load_settings


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
    monkeypatch.setenv("VERSION", "8.3.1")
    monkeypatch.setenv("API_VERSION", "v4")

    s = load_settings(env_file)
    assert str(s.host) == "https://env.example.test/"
    assert s.username == "env_user"
    assert s.password == "env_pass"
    assert s.version == "8.3.1"


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


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        ("8.3.1", 10),
        ("8.1.3", 10),
        ("8.0.0", 10),
        ("7.3.2", 0),
        ("7.3.4", 0),
        ("banana", 10),
    ],
)
def test_effective_min_password_length_follows_domjudge_version(
    version: str,
    expected: int,
) -> None:
    settings = Settings(  # type: ignore[arg-type]
        host="https://example.test",
        username="user",
        password="password",
        version=version,
        api_version="v4",
    )

    assert settings.effective_min_password_length == expected


def test_explicit_min_password_length_overrides_version_default(
    tmp_path: Path,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        """HOST=https://example.test
USERNAME=user
PASSWORD=password
VERSION=8.3.1
API_VERSION=v4
MIN_PASSWORD_LENGTH=25
""",
        encoding="utf-8",
    )

    settings = load_settings(env_file)

    assert settings.effective_min_password_length == 25


def test_negative_min_password_length_is_clamped_to_zero() -> None:
    settings = Settings(  # type: ignore[arg-type]
        host="https://example.test",
        username="user",
        password="password",
        version="8.3.1",
        api_version="v4",
        min_password_length=-5,
    )

    assert settings.effective_min_password_length == 0


def test_server_value_floors_a_lower_configured_value() -> None:
    """The server rejects shorter passwords regardless of configuration.

    If the form advertised the lower configured value it would promise a policy
    that fails after the team and user already exist.
    """
    settings = Settings(  # type: ignore[arg-type]
        host="https://example.test",
        username="user",
        password="password",
        version="8.3.1",
        api_version="v4",
        min_password_length=4,
        detected_min_password_length=10,
    )

    assert settings.effective_min_password_length == 10


def test_configured_value_may_raise_the_server_floor() -> None:
    """An operator may enforce something stricter than the server does."""
    settings = Settings(  # type: ignore[arg-type]
        host="https://example.test",
        username="user",
        password="password",
        version="8.3.1",
        api_version="v4",
        min_password_length=25,
        detected_min_password_length=10,
    )

    assert settings.effective_min_password_length == 25


def test_without_a_server_value_the_configured_value_applies() -> None:
    settings = Settings(  # type: ignore[arg-type]
        host="https://example.test",
        username="user",
        password="password",
        version="8.3.1",
        api_version="v4",
        min_password_length=4,
    )

    assert settings.effective_min_password_length == 4


def test_server_value_applies_when_nothing_is_configured() -> None:
    settings = Settings(  # type: ignore[arg-type]
        host="https://example.test",
        username="user",
        password="password",
        version="7.3.2",  # version default would be 0
        api_version="v4",
        detected_min_password_length=12,
    )

    assert settings.effective_min_password_length == 12
