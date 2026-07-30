from pathlib import Path

from fastapi import APIRouter, Depends, File, Header, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_api_or_current_user,
    get_current_user,
    verify_csrf,
    verify_csrf_or_api_key,
)
from app.core.config import get_settings
from app.core.database import get_db
from app.core.errors import AppError
from app.core.security import hash_api_key, utc_now
from app.models import AnalysisJob, ApiKey, ApiUsageLog, SongAnalysis, UploadedFile, User
from app.schemas.api import HistoryList, Message, SongAnalysisResponse
from app.services.analysis_queue import get_analysis_queue
from app.services.analyzer import analyze_audio
from app.services.points import apply_points
from app.services.report import create_analysis_report
from app.services.storage import persist_upload

settings = get_settings()
router = APIRouter(prefix="/songs", tags=["音源解析"])
analysis_queue = get_analysis_queue()


def owned_analysis(db: Session, user_id: int, analysis_id: int) -> SongAnalysis:
    analysis = db.scalar(
        select(SongAnalysis).where(SongAnalysis.id == analysis_id, SongAnalysis.user_id == user_id)
    )
    if analysis is None:
        raise AppError(404, "ANALYSIS_NOT_FOUND", "解析履歴が見つかりません。")
    return analysis


def must_get_analysis(db: Session, analysis_id: int) -> SongAnalysis:
    analysis = db.get(SongAnalysis, analysis_id)
    if analysis is None:
        raise RuntimeError(f"解析データ {analysis_id} が処理中に見つからなくなりました。")
    return analysis


def must_get_job(db: Session, analysis_id: int) -> AnalysisJob:
    job = db.scalar(select(AnalysisJob).where(AnalysisJob.analysis_id == analysis_id))
    if job is None:
        raise RuntimeError(f"解析ジョブ {analysis_id} が処理中に見つからなくなりました。")
    return job


def record_api_usage(db: Session, api_key_value: str | None, status_code: int, points_cost: int) -> None:
    if not api_key_value:
        return
    key = db.scalar(select(ApiKey).where(ApiKey.key_hash == hash_api_key(api_key_value)))
    if key:
        key.last_used_at = utc_now()
        db.add(
            ApiUsageLog(
                api_key_id=key.id,
                endpoint="/api/v1/songs/analyze",
                status_code=status_code,
                points_cost=points_cost,
            )
        )


@router.post("/analyze", response_model=SongAnalysisResponse, status_code=201)
def analyze(
    file: UploadFile = File(...),
    api_key_value: str | None = Header(default=None, alias="X-API-Key"),
    _: None = Depends(verify_csrf_or_api_key),
    user: User = Depends(get_api_or_current_user),
    db: Session = Depends(get_db),
) -> SongAnalysis:
    stored = persist_upload(file)
    uploaded = UploadedFile(
        user_id=user.id,
        original_filename=stored.original_filename,
        storage_path=str(stored.path),
        file_size=stored.file_size,
        mime_type=stored.mime_type,
        sha256=stored.digest,
    )
    db.add(uploaded)
    db.flush()
    analysis = SongAnalysis(
        user_id=user.id,
        uploaded_file_id=uploaded.id,
        original_filename=stored.original_filename,
        file_hash=stored.digest,
        file_format=stored.file_format,
        file_size=stored.file_size,
        status="QUEUED",
    )
    db.add(analysis)
    db.flush()
    job = AnalysisJob(analysis_id=analysis.id, status="QUEUED")
    db.add(job)
    db.commit()
    analysis_id = analysis.id
    try:
        with analysis_queue.acquire():
            analysis = must_get_analysis(db, analysis_id)
            analysis.status = "PROCESSING"
            job = must_get_job(db, analysis_id)
            job.status = "PROCESSING"
            job.started_at = utc_now()
            db.commit()
            result = analyze_audio(stored.path)
        analysis = must_get_analysis(db, analysis_id)
        for key, value in result.items():
            setattr(analysis, key, value)
        if settings.analysis_points_cost:
            apply_points(
                db,
                user.id,
                -settings.analysis_points_cost,
                "ANALYSIS",
                "音源解析",
                "song_analysis",
                analysis.id,
            )
        analysis.points_cost = settings.analysis_points_cost
        analysis.status = "SUCCESS"
        job = must_get_job(db, analysis_id)
        job.status = "SUCCESS"
        job.finished_at = utc_now()
        record_api_usage(db, api_key_value, 201, settings.analysis_points_cost)
        db.commit()
        db.refresh(analysis)
        return analysis
    except AppError as exc:
        db.rollback()
        failed = must_get_analysis(db, analysis_id)
        failed.status = "FAILED"
        failed.error_message = exc.message
        failed_job = must_get_job(db, analysis_id)
        failed_job.status = "FAILED"
        failed_job.error_message = exc.message
        failed_job.finished_at = utc_now()
        record_api_usage(db, api_key_value, exc.status_code, 0)
        db.commit()
        raise
    except Exception as exc:
        db.rollback()
        failed = must_get_analysis(db, analysis_id)
        failed.status = "FAILED"
        failed.error_message = "解析処理で予期しないエラーが発生しました。"
        failed_job = must_get_job(db, analysis_id)
        failed_job.status = "FAILED"
        failed_job.error_message = failed.error_message
        failed_job.finished_at = utc_now()
        record_api_usage(db, api_key_value, 422, 0)
        db.commit()
        raise AppError(422, "AUDIO_ANALYSIS_FAILED", failed.error_message or "解析処理に失敗しました。") from exc
    finally:
        Path(stored.path).unlink(missing_ok=True)
        retained = db.get(UploadedFile, uploaded.id)
        if retained:
            retained.storage_path = None
            retained.deleted_at = utc_now()
            db.commit()


@router.get("/history", response_model=HistoryList)
def history(
    filename: str | None = None,
    musical_key: str | None = Query(default=None, alias="key"),
    bpm_min: float | None = None,
    bpm_max: float | None = None,
    status: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HistoryList:
    query = select(SongAnalysis).where(SongAnalysis.user_id == user.id)
    if filename:
        query = query.where(SongAnalysis.original_filename.like(f"%{filename}%"))
    if musical_key:
        query = query.where(SongAnalysis.musical_key == musical_key)
    if bpm_min is not None:
        query = query.where(SongAnalysis.bpm >= bpm_min)
    if bpm_max is not None:
        query = query.where(SongAnalysis.bpm <= bpm_max)
    if status:
        query = query.where(SongAnalysis.status == status)
    items = list(db.scalars(query.order_by(desc(SongAnalysis.created_at)).limit(100)))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    return HistoryList(items=[SongAnalysisResponse.model_validate(item) for item in items], total=total)


@router.get("/history/{analysis_id}", response_model=SongAnalysisResponse)
def detail(
    analysis_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SongAnalysis:
    return owned_analysis(db, user.id, analysis_id)


@router.delete("/history/{analysis_id}", response_model=Message)
def delete_history(
    analysis_id: int,
    _: None = Depends(verify_csrf),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Message:
    analysis = owned_analysis(db, user.id, analysis_id)
    job = db.scalar(select(AnalysisJob).where(AnalysisJob.analysis_id == analysis.id))
    if job:
        db.delete(job)
    db.delete(analysis)
    db.commit()
    return Message(message="解析履歴を削除しました。")


@router.get("/history/{analysis_id}/report")
def report(
    analysis_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    analysis = owned_analysis(db, user.id, analysis_id)
    if analysis.status != "SUCCESS":
        raise AppError(409, "REPORT_UNAVAILABLE", "成功した解析のみレポートを出力できます。")
    filename = f"analysis-report-{analysis.id}.pdf"
    return StreamingResponse(
        create_analysis_report(analysis, user.username),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
