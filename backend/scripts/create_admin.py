import os

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import User
from sqlalchemy import select


def main() -> None:
    """環境変数で指定された初回管理者を安全に作成または昇格する。"""
    email = os.environ.get("AUDIO_ADMIN_EMAIL", "").strip().lower()
    password = os.environ.get("AUDIO_ADMIN_PASSWORD", "")
    username = os.environ.get("AUDIO_ADMIN_USERNAME", "管理者")
    if not email or len(password) < 12:
        raise SystemExit("AUDIO_ADMIN_EMAIL と 12 文字以上の AUDIO_ADMIN_PASSWORD を設定してください。")
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(
                email=email,
                username=username,
                hashed_password=hash_password(password),
                role="ADMIN",
                status="ACTIVE",
            )
            db.add(user)
        else:
            user.role = "ADMIN"
            user.hashed_password = hash_password(password)
            user.status = "ACTIVE"
        db.commit()
    print("管理者アカウントを作成または更新しました。")


if __name__ == "__main__":
    main()
