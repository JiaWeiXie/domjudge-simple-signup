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
