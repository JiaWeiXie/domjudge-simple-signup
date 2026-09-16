import re

from pydantic import BaseModel, EmailStr, Field, field_validator

# DOMjudge's Team::validate() rejects any other character with a 422 when a new
# user is created for the team, which surfaces to the applicant as a raw error
# page, so refuse the same characters up front.
USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


def normalize_username(value: str) -> str:
    """Trim the username the way DOMjudge's form trimming does.

    DOMjudge trims submitted form values before storing them, so the app must
    use the trimmed value for the duplicate check, the rollback identity and
    the team display name.
    """
    return value.strip()


class NewUser(BaseModel):
    username: str
    name: str
    email: EmailStr
    password: str
    enabled: bool = True
    roles: list[str] = Field(default_factory=list)
    team_id: str | None = None
    team: str | None = None
    affiliation: str | None = None

    @field_validator("username", mode="after")
    @classmethod
    def _validate_username(cls, value: str) -> str:
        normalized = normalize_username(value)
        if not USERNAME_PATTERN.fullmatch(normalized):
            raise ValueError("只能使用英文字母、數字、底線與減號")
        return normalized
