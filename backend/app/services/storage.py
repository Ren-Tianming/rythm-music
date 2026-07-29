import uuid
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from fastapi import UploadFile

from app.core.config import get_settings
from app.core.errors import AppError

settings = get_settings()
ALLOWED_SUFFIXES = {".mp3", ".wav", ".flac", ".m4a"}
ALLOWED_MIME_TYPES = {
    "audio/mpeg",
    "audio/wav",
    "audio/x-wav",
    "audio/flac",
    "audio/x-flac",
    "audio/mp4",
    "audio/x-m4a",
    "application/octet-stream",
}


@dataclass
class StoredUpload:
    path: Path
    original_filename: str
    file_format: str
    file_size: int
    mime_type: str
    digest: str


def persist_upload(file: UploadFile) -> StoredUpload:
    original_name = Path(file.filename or "upload").name
    suffix = Path(original_name).suffix.lower()
    mime_type = file.content_type or "application/octet-stream"
    if suffix not in ALLOWED_SUFFIXES or mime_type not in ALLOWED_MIME_TYPES:
        raise AppError(415, "UNSUPPORTED_FILE_FORMAT", "対応形式は MP3、WAV、FLAC、M4A です。")

    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    target = settings.upload_dir / f"{uuid.uuid4().hex}{suffix}"
    digest = sha256()
    size = 0
    try:
        with target.open("wb") as output:
            while chunk := file.file.read(1024 * 1024):
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    raise AppError(413, "FILE_TOO_LARGE", "ファイルサイズが上限を超えています。")
                digest.update(chunk)
                output.write(chunk)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return StoredUpload(target, original_name, suffix.removeprefix("."), size, mime_type, digest.hexdigest())
