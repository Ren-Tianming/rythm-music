from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import PointTransaction, User


def apply_points(
    db: Session,
    user_id: int,
    change: int,
    transaction_type: str,
    description: str,
    related_type: str | None = None,
    related_id: int | None = None,
) -> User:
    user = db.scalar(select(User).where(User.id == user_id).with_for_update())
    if user is None:
        raise AppError(404, "USER_NOT_FOUND", "ユーザーが見つかりません。")
    balance_before = user.points_balance
    balance_after = balance_before + change
    if balance_after < 0:
        raise AppError(409, "INSUFFICIENT_POINTS", "ポイント残高が不足しています。")
    user.points_balance = balance_after
    db.add(
        PointTransaction(
            user_id=user_id,
            transaction_type=transaction_type,
            points_change=change,
            balance_before=balance_before,
            balance_after=balance_after,
            related_type=related_type,
            related_id=related_id,
            description=description,
        )
    )
    return user
