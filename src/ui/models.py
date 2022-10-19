from typing import List, Optional

from pydantic import BaseModel, EmailStr


class NewUser(BaseModel):
    username: str
    name: str
    email: EmailStr
    password: str
    enabled: bool = True
    roles: List[str] = []
    team_id: Optional[str]
    team: Optional[str]
    affiliation: Optional[str] = None
