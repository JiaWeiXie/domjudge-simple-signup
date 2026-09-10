from pydantic import BaseModel, EmailStr, Field


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
