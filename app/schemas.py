from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl, field_validator


ALLOWED_STATUSES = {"open", "applied", "in_progress", "won", "lost"}


class UserCreate(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    password: str = Field(min_length=8, max_length=128)
    wallet_address: str | None = Field(default=None, max_length=120)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    username: str
    wallet_address: str | None
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class BountyBase(BaseModel):
    title: str = Field(min_length=3, max_length=150)
    platform: str = Field(default="Gitcoin", min_length=2, max_length=80)
    reward_usd: int = Field(default=0, ge=0)
    status: str = Field(default="open")
    url: HttpUrl | None = None
    skills: str = Field(default="", max_length=300)
    notes: str = ""
    deadline: datetime | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in ALLOWED_STATUSES:
            raise ValueError(
                "status must be one of: open, applied, in_progress, won, lost"
            )
        return normalized

    @field_validator("deadline")
    @classmethod
    def validate_deadline(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return value

        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)

        if value <= datetime.now(timezone.utc):
            raise ValueError("deadline must be in the future")

        return value


class BountyCreate(BountyBase):
    pass


class BountyUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=150)
    platform: str | None = Field(default=None, min_length=2, max_length=80)
    reward_usd: int | None = Field(default=None, ge=0)
    status: str | None = None
    url: HttpUrl | None = None
    skills: str | None = Field(default=None, max_length=300)
    notes: str | None = None
    deadline: datetime | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if normalized not in ALLOWED_STATUSES:
            raise ValueError(
                "status must be one of: open, applied, in_progress, won, lost"
            )
        return normalized

    @field_validator("deadline")
    @classmethod
    def validate_deadline(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None

        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)

        if value <= datetime.now(timezone.utc):
            raise ValueError("deadline must be in the future")

        return value


class BountyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    title: str
    platform: str
    reward_usd: int
    status: str
    url: str | None
    skills: str
    notes: str
    deadline: datetime | None
    created_at: datetime
    updated_at: datetime


class PaginationMeta(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int


class PaginatedBounties(BaseModel):
    items: list[BountyResponse]
    meta: PaginationMeta


class StatsResponse(BaseModel):
    total_bounties: int
    total_reward_usd: int
    won_reward_usd: int
    by_status: dict[str, int]
