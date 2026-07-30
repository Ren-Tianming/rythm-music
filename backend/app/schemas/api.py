from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.core.security import validate_display_name, validate_password_strength

SUPPORTED_LOCALES = {"zh-CN", "ja-JP", "en-US"}


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Message(BaseModel):
    message: str


class UserCreate(BaseModel):
    email: EmailStr
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=12, max_length=128)
    password_confirmation: str = Field(min_length=12, max_length=128)
    locale: str = "zh-CN"
    terms_version: str = Field(min_length=1, max_length=40)
    terms_accepted: bool
    turnstile_token: str | None = Field(default=None, max_length=2048)

    @field_validator("username")
    @classmethod
    def valid_username(cls, value: str) -> str:
        return validate_display_name(value)

    @field_validator("password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        return validate_password_strength(value)

    @field_validator("locale")
    @classmethod
    def valid_locale(cls, value: str) -> str:
        if value not in SUPPORTED_LOCALES:
            raise ValueError("Unsupported locale")
        return value

    @model_validator(mode="after")
    def consent_and_passwords_match(self) -> "UserCreate":
        if self.password != self.password_confirmation:
            raise ValueError("Passwords do not match")
        if not self.terms_accepted:
            raise ValueError("Terms must be accepted")
        return self


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    turnstile_token: str | None = Field(default=None, max_length=2048)


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=20, max_length=300)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr
    turnstile_token: str | None = Field(default=None, max_length=2048)


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=20, max_length=300)
    password: str = Field(min_length=12, max_length=128)
    password_confirmation: str = Field(min_length=12, max_length=128)

    @field_validator("password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        return validate_password_strength(value)

    @model_validator(mode="after")
    def passwords_match(self) -> "ResetPasswordRequest":
        if self.password != self.password_confirmation:
            raise ValueError("Passwords do not match")
        return self


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)
    new_password_confirmation: str = Field(min_length=12, max_length=128)

    @field_validator("new_password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        return validate_password_strength(value)

    @model_validator(mode="after")
    def passwords_match(self) -> "PasswordChange":
        if self.new_password != self.new_password_confirmation:
            raise ValueError("Passwords do not match")
        return self


class ProfileUpdate(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    locale: str | None = None

    @field_validator("username")
    @classmethod
    def valid_username(cls, value: str) -> str:
        return validate_display_name(value)

    @field_validator("locale")
    @classmethod
    def valid_locale(cls, value: str | None) -> str | None:
        if value is not None and value not in SUPPORTED_LOCALES:
            raise ValueError("Unsupported locale")
        return value


class UserResponse(ORMModel):
    id: int
    email: str
    username: str
    locale: str
    role: str
    status: str
    points_balance: int
    is_email_verified: bool
    email_verified_at: datetime | None
    last_login_at: datetime | None
    created_at: datetime


class SessionResponse(BaseModel):
    """Browser response for an HttpOnly opaque server-side session."""

    user: UserResponse
    daily_bonus_awarded: int = 0


class BrowserSessionResponse(BaseModel):
    id: str
    user_agent: str | None
    ip_address: str | None
    last_seen_at: datetime
    created_at: datetime
    current: bool = False


class BalanceResponse(BaseModel):
    points_balance: int
    analysis_cost: int


class PointTransactionResponse(ORMModel):
    id: int
    transaction_type: str
    points_change: int
    balance_before: int
    balance_after: int
    description: str
    created_at: datetime


class SongAnalysisResponse(ORMModel):
    id: int
    original_filename: str
    file_hash: str
    file_format: str
    file_size: int
    duration_sec: Decimal | None
    sample_rate: int | None
    channels: int | None
    bpm: Decimal | None
    musical_key: str | None
    lufs: Decimal | None
    rms: Decimal | None
    waveform: list[float] | None
    spectrogram: list[list[float]] | None
    genre: str | None
    genre_confidence: Decimal | None
    genre_model_status: str
    genre_model_version: str | None
    lyrics: str | None
    lyrics_status: str
    ai_summary: str | None
    ai_summary_source: str
    status: str
    points_cost: int
    error_message: str | None
    created_at: datetime


class HistoryList(BaseModel):
    items: list[SongAnalysisResponse]
    total: int


class GenerationCreate(BaseModel):
    prompt: str = Field(min_length=3, max_length=1000)
    title: str | None = Field(default=None, min_length=1, max_length=160)
    instrumental: bool = True
    duration_sec: int = Field(default=8, ge=5, le=30)


class GenerationResponse(ORMModel):
    id: int
    title: str
    prompt: str
    instrumental: bool
    duration_sec: int
    provider: str
    provider_job_id: str | None
    status: str
    audio_url: str | None
    points_cost: int
    error_message: str | None
    created_at: datetime


class WorkCreate(BaseModel):
    generation_id: int
    title: str | None = Field(default=None, min_length=1, max_length=160)
    description: str = Field(default="", max_length=1000)
    cover_gradient: str = Field(default="violet", pattern="^(violet|cyan|sunset|midnight)$")


class WorkResponse(BaseModel):
    id: int
    generation_id: int
    title: str
    description: str
    cover_gradient: str
    likes_count: int
    audio_url: str | None
    creator_name: str
    created_at: datetime


class FounderProfile(BaseModel):
    artist_name: str
    tagline: str
    bio: str
    styles: list[str]


class PackageResponse(ORMModel):
    id: int
    name: str
    points: int
    price: Decimal
    currency: str
    is_active: bool


class PlanResponse(ORMModel):
    id: int
    name: str
    monthly_price: Decimal
    monthly_points: int
    history_limit: int | None
    api_limit: int
    is_active: bool


class OrderCreate(BaseModel):
    package_id: int


class OrderResponse(ORMModel):
    id: int
    package_id: int
    amount: Decimal
    currency: str
    points_granted: int
    status: str
    paid_at: datetime | None
    created_at: datetime


class SubscriptionCreate(BaseModel):
    plan_id: int


class CouponRedeem(BaseModel):
    code: str = Field(min_length=1, max_length=50)


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class ApiKeyResponse(ORMModel):
    id: int
    key_prefix: str
    name: str
    status: str
    last_used_at: datetime | None
    created_at: datetime


class ApiKeyIssued(ApiKeyResponse):
    api_key: str


class AdminStatusUpdate(BaseModel):
    status: str = Field(pattern="^(ACTIVE|DISABLED)$")


class AdminRoleUpdate(BaseModel):
    role: str = Field(pattern="^(USER|ADMIN)$")


class AdminPointsUpdate(BaseModel):
    points_change: int
    reason: str = Field(min_length=2, max_length=255)


class AdminOrderStatusUpdate(BaseModel):
    status: str = Field(pattern="^(PAID|CANCELED|FAILED|REFUNDED)$")


class SettingUpdate(BaseModel):
    setting_value: str = Field(min_length=1, max_length=255)


class SettingResponse(ORMModel):
    setting_key: str
    setting_value: str
    description: str
    updated_at: datetime


class AdminCouponCreate(BaseModel):
    code: str = Field(min_length=2, max_length=50)
    value: int = Field(gt=0)
    expires_at: datetime | None = None
    max_redemptions: int | None = Field(default=None, gt=0)


class AdminCouponResponse(ORMModel):
    id: int
    code: str
    coupon_type: str
    value: int
    expires_at: datetime | None
    max_redemptions: int | None
    is_active: bool


class AdminPlanUpdate(BaseModel):
    monthly_price: Decimal = Field(ge=0)
    monthly_points: int = Field(ge=0)
    history_limit: int | None = Field(default=None, gt=0)
    api_limit: int = Field(ge=0)
    is_active: bool
