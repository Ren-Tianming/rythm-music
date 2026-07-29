from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, verify_csrf
from app.core.config import get_settings
from app.core.database import get_db
from app.models import PointTransaction, User
from app.schemas.api import BalanceResponse, PointTransactionResponse, ProfileUpdate, UserResponse

settings = get_settings()
router = APIRouter(tags=["ユーザー・ポイント"])


@router.get("/users/me", response_model=UserResponse)
def profile(user: User = Depends(get_current_user)) -> User:
    return user


@router.patch("/users/me", response_model=UserResponse)
def update_profile(
    payload: ProfileUpdate,
    _: None = Depends(verify_csrf),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    user.username = payload.username
    db.commit()
    db.refresh(user)
    return user


@router.get("/points/balance", response_model=BalanceResponse)
def balance(user: User = Depends(get_current_user)) -> BalanceResponse:
    return BalanceResponse(points_balance=user.points_balance, analysis_cost=settings.analysis_points_cost)


@router.get("/points/transactions", response_model=list[PointTransactionResponse])
def transactions(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PointTransaction]:
    return list(
        db.scalars(
            select(PointTransaction)
            .where(PointTransaction.user_id == user.id)
            .order_by(desc(PointTransaction.created_at))
            .limit(100)
        )
    )
