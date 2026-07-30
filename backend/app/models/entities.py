from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.security import utc_now

SQLITE_COMPATIBLE_ID = BigInteger().with_variant(Integer, "sqlite")


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("points_balance >= 0", name="ck_users_points_non_negative"),)

    id: Mapped[int] = mapped_column(SQLITE_COMPATIBLE_ID, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    locale: Mapped[str] = mapped_column(String(10), default="zh-CN", nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="USER", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)
    points_balance: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    point_transactions: Mapped[list["PointTransaction"]] = relationship(back_populates="user")
    analyses: Mapped[list["SongAnalysis"]] = relationship(back_populates="user")
    auth_sessions: Mapped[list["AuthSession"]] = relationship(cascade="all, delete-orphan")
    email_verification_tokens: Mapped[list["EmailVerificationToken"]] = relationship(
        cascade="all, delete-orphan"
    )
    password_reset_tokens: Mapped[list["PasswordResetToken"]] = relationship(
        cascade="all, delete-orphan"
    )
    consents: Mapped[list["UserConsent"]] = relationship(cascade="all, delete-orphan")
    audit_logs: Mapped[list["AuditLog"]] = relationship()
    generations: Mapped[list["GeneratedTrack"]] = relationship(back_populates="user")
    published_works: Mapped[list["PublishedWork"]] = relationship(back_populates="user")
    work_likes: Mapped[list["PublishedWorkLike"]] = relationship(back_populates="user")


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    __table_args__ = (Index("ix_auth_sessions_user_expires", "user_id", "expires_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    csrf_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class EmailVerificationToken(Base):
    __tablename__ = "email_verification_tokens"
    __table_args__ = (
        Index("ix_email_verification_user_expires", "user_id", "expires_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    __table_args__ = (
        Index("ix_password_reset_user_expires", "user_id", "expires_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class UserConsent(Base):
    __tablename__ = "user_consents"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "document_type",
            "document_version",
            name="uq_user_consents_document_version",
        ),
    )

    id: Mapped[int] = mapped_column(SQLITE_COMPATIBLE_ID, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    document_type: Mapped[str] = mapped_column(String(40), nullable=False)
    document_version: Mapped[str] = mapped_column(String(40), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    consented_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_event_created", "event_type", "created_at"),)

    id: Mapped[int] = mapped_column(SQLITE_COMPATIBLE_ID, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    result: Mapped[str] = mapped_column(String(20), default="success", nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    metadata_redacted: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class DailyLoginReward(Base):
    __tablename__ = "daily_login_rewards"
    __table_args__ = (UniqueConstraint("user_id", "reward_date", name="uq_daily_reward_user_date"),)

    id: Mapped[int] = mapped_column(SQLITE_COMPATIBLE_ID, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    reward_date: Mapped[date] = mapped_column(Date, nullable=False)
    points_awarded: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class PointTransaction(Base):
    __tablename__ = "point_transactions"
    __table_args__ = (Index("ix_point_transactions_user_created", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(SQLITE_COMPATIBLE_ID, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(50), nullable=False)
    points_change: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_before: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    related_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    related_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    user: Mapped[User] = relationship(back_populates="point_transactions")


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id: Mapped[int] = mapped_column(SQLITE_COMPATIBLE_ID, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    retention_policy: Mapped[str] = mapped_column(String(30), default="DELETE_AFTER_ANALYSIS", nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class SongAnalysis(TimestampMixin, Base):
    __tablename__ = "song_analyses"
    __table_args__ = (Index("ix_song_analyses_user_created", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(SQLITE_COMPATIBLE_ID, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    uploaded_file_id: Mapped[int | None] = mapped_column(ForeignKey("uploaded_files.id"), nullable=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    file_format: Mapped[str] = mapped_column(String(20), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    duration_sec: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    sample_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    channels: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bpm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    musical_key: Mapped[str | None] = mapped_column(String(20), nullable=True)
    lufs: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), nullable=True)
    rms: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    waveform: Mapped[list[float] | None] = mapped_column(JSON, nullable=True)
    spectrogram: Mapped[list[list[float]] | None] = mapped_column(JSON, nullable=True)
    genre: Mapped[str | None] = mapped_column(String(100), nullable=True)
    genre_confidence: Mapped[Decimal | None] = mapped_column(Numeric(6, 5), nullable=True)
    genre_model_status: Mapped[str] = mapped_column(String(30), default="NOT_CONFIGURED", nullable=False)
    genre_model_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    lyrics: Mapped[str | None] = mapped_column(Text, nullable=True)
    lyrics_status: Mapped[str] = mapped_column(String(30), default="NOT_CONFIGURED", nullable=False)
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_summary_source: Mapped[str] = mapped_column(String(30), default="LOCAL", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False)
    points_cost: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped[User] = relationship(back_populates="analyses")


class GeneratedTrack(TimestampMixin, Base):
    __tablename__ = "generated_tracks"
    __table_args__ = (Index("ix_generated_tracks_user_created", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(SQLITE_COMPATIBLE_ID, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    instrumental: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    duration_sec: Mapped[int] = mapped_column(Integer, default=8, nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    provider_job_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="PENDING", nullable=False)
    audio_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    points_cost: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped[User] = relationship(back_populates="generations")
    published_work: Mapped["PublishedWork | None"] = relationship(
        back_populates="generation", uselist=False
    )


class PublishedWork(TimestampMixin, Base):
    __tablename__ = "published_works"
    __table_args__ = (
        Index("ix_published_works_public_created", "is_public", "created_at"),
        UniqueConstraint("generation_id", name="uq_published_work_generation"),
    )

    id: Mapped[int] = mapped_column(SQLITE_COMPATIBLE_ID, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    generation_id: Mapped[int] = mapped_column(ForeignKey("generated_tracks.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    cover_gradient: Mapped[str] = mapped_column(String(80), default="violet", nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    likes_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    user: Mapped[User] = relationship(back_populates="published_works")
    generation: Mapped[GeneratedTrack] = relationship(back_populates="published_work")
    likes: Mapped[list["PublishedWorkLike"]] = relationship(back_populates="work")


class PublishedWorkLike(Base):
    __tablename__ = "published_work_likes"
    __table_args__ = (UniqueConstraint("work_id", "user_id", name="uq_published_work_like_user"),)

    id: Mapped[int] = mapped_column(SQLITE_COMPATIBLE_ID, primary_key=True, autoincrement=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("published_works.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    work: Mapped[PublishedWork] = relationship(back_populates="likes")
    user: Mapped[User] = relationship(back_populates="work_likes")


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"

    id: Mapped[int] = mapped_column(SQLITE_COMPATIBLE_ID, primary_key=True, autoincrement=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("song_analyses.id"), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class PointPackage(Base):
    __tablename__ = "point_packages"

    id: Mapped[int] = mapped_column(SQLITE_COMPATIBLE_ID, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="JPY", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class PaymentOrder(Base):
    __tablename__ = "payment_orders"
    __table_args__ = (Index("ix_payment_orders_user_status", "user_id", "status"),)

    id: Mapped[int] = mapped_column(SQLITE_COMPATIBLE_ID, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    package_id: Mapped[int] = mapped_column(ForeignKey("point_packages.id"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="JPY", nullable=False)
    points_granted: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(SQLITE_COMPATIBLE_ID, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    monthly_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    monthly_points: Mapped[int] = mapped_column(Integer, nullable=False)
    history_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    api_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(SQLITE_COMPATIBLE_ID, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)
    current_period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    current_period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class Coupon(Base):
    __tablename__ = "coupons"

    id: Mapped[int] = mapped_column(SQLITE_COMPATIBLE_ID, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    coupon_type: Mapped[str] = mapped_column(String(20), nullable=False)
    value: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    max_redemptions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class CouponRedemption(Base):
    __tablename__ = "coupon_redemptions"
    __table_args__ = (UniqueConstraint("coupon_id", "user_id", name="uq_coupon_user"),)

    id: Mapped[int] = mapped_column(SQLITE_COMPATIBLE_ID, primary_key=True, autoincrement=True)
    coupon_id: Mapped[int] = mapped_column(ForeignKey("coupons.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    redeemed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(SQLITE_COMPATIBLE_ID, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class ApiUsageLog(Base):
    __tablename__ = "api_usage_logs"

    id: Mapped[int] = mapped_column(SQLITE_COMPATIBLE_ID, primary_key=True, autoincrement=True)
    api_key_id: Mapped[int] = mapped_column(ForeignKey("api_keys.id"), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    points_cost: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_logs"
    __table_args__ = (Index("ix_admin_audit_user_created", "admin_user_id", "created_at"),)

    id: Mapped[int] = mapped_column(SQLITE_COMPATIBLE_ID, primary_key=True, autoincrement=True)
    admin_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class SystemSetting(Base):
    __tablename__ = "system_settings"

    setting_key: Mapped[str] = mapped_column(String(100), primary_key=True)
    setting_value: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
