import pytest
from pydantic import ValidationError

from ui.models import NewUser


def test_new_user_valid() -> None:
    u = NewUser(
        username="john_doe",
        name="John Doe",
        email="john@example.com",  # type: ignore[arg-type]
        password="secret_password",
    )
    assert u.username == "john_doe"
    assert u.name == "John Doe"
    assert u.email == "john@example.com"
    assert u.enabled is True
    assert u.roles == []
    assert u.team_id is None
    assert u.team is None
    assert u.affiliation is None


def test_new_user_validation_error_on_invalid_email() -> None:
    with pytest.raises(ValidationError):
        NewUser(
            username="john",
            name="John",
            email="not-an-email",  # type: ignore[arg-type]
            password="pwd",
        )


def test_new_user_roles_list_isolation() -> None:
    u1 = NewUser(
        username="u1",
        name="User 1",
        email="u1@example.com",  # type: ignore[arg-type]
        password="p1",
    )
    u2 = NewUser(
        username="u2",
        name="User 2",
        email="u2@example.com",  # type: ignore[arg-type]
        password="p2",
    )
    u1.roles.append("role1")
    assert u2.roles == []


def test_username_is_trimmed_like_domjudge_trimming() -> None:
    """DOMjudge trims submitted form values before storing them."""
    u = NewUser(
        username="  john_doe  ",
        name="John Doe",
        email="john@example.com",  # type: ignore[arg-type]
        password="secret_password",
    )
    assert u.username == "john_doe"


@pytest.mark.parametrize(
    "username",
    ["bad name", "bad.name", "bad@name", "王小明", "bad/name", "bad+name", ""],
)
def test_username_rejects_characters_domjudge_refuses(username: str) -> None:
    """DOMjudge's Team::validate() only allows [a-zA-Z0-9_-] for a new user."""
    with pytest.raises(ValidationError):
        NewUser(
            username=username,
            name="Someone",
            email="a@example.com",  # type: ignore[arg-type]
            password="secret_password",
        )


@pytest.mark.parametrize("username", ["john_doe", "john-doe", "john123", "JD42"])
def test_username_accepts_domjudge_allowed_characters(username: str) -> None:
    u = NewUser(
        username=username,
        name="Someone",
        email="a@example.com",  # type: ignore[arg-type]
        password="secret_password",
    )
    assert u.username == username
