from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Plan, PointPackage, SystemSetting


def seed_master_data(db: Session) -> None:
    if not db.scalar(select(PointPackage.id).limit(1)):
        db.add_all(
            [
                PointPackage(name="パルス 100", points=100, price=Decimal("980"), currency="JPY"),
                PointPackage(name="ボルテージ 500", points=500, price=Decimal("3980"), currency="JPY"),
                PointPackage(name="インフィニティ 1000", points=1000, price=Decimal("6980"), currency="JPY"),
            ]
        )
    if not db.scalar(select(Plan.id).limit(1)):
        db.add_all(
            [
                Plan(name="無料", monthly_price=0, monthly_points=0, history_limit=100, api_limit=0),
                Plan(name="クリエイター", monthly_price=980, monthly_points=120, history_limit=500, api_limit=100),
                Plan(name="プロ", monthly_price=2480, monthly_points=400, history_limit=None, api_limit=1000),
                Plan(name="スタジオ", monthly_price=6980, monthly_points=1200, history_limit=None, api_limit=10000),
            ]
        )
    defaults = {
        "analysis_points_cost": ("5", "音源解析一回あたりの消費ポイント"),
        "generation_points_cost": ("10", "外部音楽生成一回あたりの消費ポイント"),
        "max_upload_bytes": ("52428800", "アップロード可能な最大ファイルサイズ"),
        "max_audio_duration_sec": ("600", "解析可能な最大秒数"),
    }
    for key, (value, description) in defaults.items():
        if db.get(SystemSetting, key) is None:
            db.add(SystemSetting(setting_key=key, setting_value=value, description=description))
    db.commit()
