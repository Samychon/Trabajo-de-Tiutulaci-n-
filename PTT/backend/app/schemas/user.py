from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=150)


class UserCreate(UserBase):
    password: str = Field(min_length=12, max_length=128)
    role_id: int


class UserUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    username: str | None = Field(default=None, min_length=3, max_length=50)
    email: EmailStr | None = None
    full_name: str | None = Field(default=None, min_length=1, max_length=150)
    password: str | None = Field(default=None, min_length=12, max_length=128)
    role_id: int | None = None


class UserDeactivateRequest(BaseModel):
    confirmation_password: str = Field(min_length=1, max_length=128)


class UserReactivateRequest(BaseModel):
    confirmation_password: str = Field(min_length=1, max_length=128)


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    is_active: bool
    role_id: int
    role_name: str


class RoleRead(BaseModel):
    id: int
    name: str
    description: str | None
