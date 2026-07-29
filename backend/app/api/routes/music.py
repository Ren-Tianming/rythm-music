from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import desc, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, verify_csrf
from app.core.config import get_settings
from app.core.database import get_db
from app.core.errors import AppError
from app.models import GeneratedTrack, PublishedWork, PublishedWorkLike, User
from app.schemas.api import (
    FounderProfile,
    GenerationCreate,
    GenerationResponse,
    WorkCreate,
    WorkResponse,
)
from app.services.generator import generate_music, get_generation_status
from app.services.points import apply_points

settings = get_settings()
router = APIRouter(prefix="/music", tags=["RyThM Music"])


def _work_response(work: PublishedWork, user: User, track: GeneratedTrack) -> WorkResponse:
    return WorkResponse(
        id=work.id,
        generation_id=track.id,
        title=work.title,
        description=work.description,
        cover_gradient=work.cover_gradient,
        likes_count=work.likes_count,
        audio_url=track.audio_url,
        creator_name=user.username,
        created_at=work.created_at,
    )


@router.post("/generations", response_model=GenerationResponse, status_code=201)
def create_generation(
    payload: GenerationCreate,
    _: None = Depends(verify_csrf),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GeneratedTrack:
    track = GeneratedTrack(
        user_id=user.id,
        title=payload.title or "Untitled RyThM",
        prompt=payload.prompt,
        instrumental=payload.instrumental,
        duration_sec=payload.duration_sec,
        provider=settings.music_provider,
        status="PROCESSING",
    )
    db.add(track)
    db.commit()
    db.refresh(track)
    try:
        result = generate_music(payload.prompt, payload.instrumental, payload.duration_sec)
        track.title = payload.title or result.title
        track.provider = result.provider
        track.provider_job_id = result.provider_job_id
        track.status = result.status
        track.audio_url = result.audio_url
        track.duration_sec = result.duration_sec
        if result.status == "SUCCESS" and settings.generation_points_cost:
            apply_points(
                db,
                user.id,
                -settings.generation_points_cost,
                "GENERATION",
                "音楽生成",
                "generated_track",
                track.id,
            )
        track.points_cost = settings.generation_points_cost if result.status == "SUCCESS" else 0
        db.commit()
        db.refresh(track)
        return track
    except AppError as exc:
        db.rollback()
        failed = db.get(GeneratedTrack, track.id)
        if failed is not None:
            failed.status = "FAILED"
            failed.error_message = exc.message
            db.commit()
        raise


@router.get("/generations", response_model=list[GenerationResponse])
def list_generations(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[GeneratedTrack]:
    return list(
        db.scalars(
            select(GeneratedTrack)
            .where(GeneratedTrack.user_id == user.id)
            .order_by(desc(GeneratedTrack.created_at))
            .limit(100)
        )
    )


@router.post("/generations/{generation_id}/refresh", response_model=GenerationResponse)
def refresh_generation(
    generation_id: int,
    _: None = Depends(verify_csrf),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GeneratedTrack:
    track = db.scalar(
        select(GeneratedTrack).where(
            GeneratedTrack.id == generation_id,
            GeneratedTrack.user_id == user.id,
        )
    )
    if track is None:
        raise AppError(404, "GENERATION_NOT_FOUND", "Generated track was not found.")
    if track.status != "PROCESSING":
        return track
    if not track.provider_job_id:
        raise AppError(409, "GENERATION_STATUS_UNAVAILABLE", "Generation has no provider job ID.")
    result = get_generation_status(track.provider_job_id, track.duration_sec)
    track.status = result.status
    track.audio_url = result.audio_url
    track.duration_sec = result.duration_sec
    if result.status == "SUCCESS" and not track.points_cost:
        if settings.generation_points_cost:
            apply_points(
                db,
                user.id,
                -settings.generation_points_cost,
                "GENERATION",
                "音楽生成",
                "generated_track",
                track.id,
            )
        track.points_cost = settings.generation_points_cost
    db.commit()
    db.refresh(track)
    return track


@router.post("/works", response_model=WorkResponse, status_code=201)
def publish_work(
    payload: WorkCreate,
    _: None = Depends(verify_csrf),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkResponse:
    track = db.scalar(
        select(GeneratedTrack).where(
            GeneratedTrack.id == payload.generation_id,
            GeneratedTrack.user_id == user.id,
        )
    )
    if track is None:
        raise AppError(404, "GENERATION_NOT_FOUND", "Generated track was not found.")
    if track.status != "SUCCESS" or not track.audio_url:
        raise AppError(409, "GENERATION_NOT_READY", "Only completed tracks can be published.")
    if db.scalar(select(PublishedWork.id).where(PublishedWork.generation_id == track.id)):
        raise AppError(409, "WORK_ALREADY_PUBLISHED", "This track is already published.")
    work = PublishedWork(
        user_id=user.id,
        generation_id=track.id,
        title=payload.title or track.title,
        description=payload.description,
        cover_gradient=payload.cover_gradient,
    )
    db.add(work)
    db.commit()
    db.refresh(work)
    return _work_response(work, user, track)


@router.get("/works", response_model=list[WorkResponse])
def public_works(db: Session = Depends(get_db)) -> list[WorkResponse]:
    rows = db.execute(
        select(PublishedWork, User, GeneratedTrack)
        .join(User, User.id == PublishedWork.user_id)
        .join(GeneratedTrack, GeneratedTrack.id == PublishedWork.generation_id)
        .where(PublishedWork.is_public.is_(True))
        .order_by(desc(PublishedWork.created_at))
        .limit(50)
    ).all()
    return [_work_response(work, user, track) for work, user, track in rows]


@router.get("/works/mine", response_model=list[WorkResponse])
def my_works(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[WorkResponse]:
    rows = db.execute(
        select(PublishedWork, GeneratedTrack)
        .join(GeneratedTrack, GeneratedTrack.id == PublishedWork.generation_id)
        .where(PublishedWork.user_id == user.id)
        .order_by(desc(PublishedWork.created_at))
    ).all()
    return [_work_response(work, user, track) for work, track in rows]


@router.post("/works/{work_id}/like", response_model=WorkResponse)
def like_work(
    work_id: int,
    _: None = Depends(verify_csrf),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkResponse:
    row = db.execute(
        select(PublishedWork, User, GeneratedTrack)
        .join(User, User.id == PublishedWork.user_id)
        .join(GeneratedTrack, GeneratedTrack.id == PublishedWork.generation_id)
        .where(PublishedWork.id == work_id, PublishedWork.is_public.is_(True))
        .with_for_update()
    ).first()
    if row is None:
        raise AppError(404, "WORK_NOT_FOUND", "Published work was not found.")
    work, user, track = row
    db.add(PublishedWorkLike(work_id=work.id, user_id=current_user.id))
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        row = db.execute(
            select(PublishedWork, User, GeneratedTrack)
            .join(User, User.id == PublishedWork.user_id)
            .join(GeneratedTrack, GeneratedTrack.id == PublishedWork.generation_id)
            .where(PublishedWork.id == work_id, PublishedWork.is_public.is_(True))
        ).first()
        if row is None:
            raise AppError(404, "WORK_NOT_FOUND", "Published work was not found.") from None
        work, user, track = row
        return _work_response(work, user, track)
    work.likes_count = int(
        db.scalar(select(func.count()).select_from(PublishedWorkLike).where(PublishedWorkLike.work_id == work.id)) or 0
    )
    work.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(work)
    return _work_response(work, user, track)


@router.get("/founder", response_model=FounderProfile)
def founder_profile() -> FounderProfile:
    return FounderProfile(
        artist_name="RyThM",
        tagline="Between machine precision and human rhythm.",
        bio="Music producer and software engineer building tools that turn sound into visible, reusable ideas.",
        styles=["Electronic", "Hip-Hop", "Cyberpunk", "Experimental"],
    )
