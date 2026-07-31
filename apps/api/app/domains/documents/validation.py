from __future__ import annotations

from pathlib import Path
from typing import Optional

from app.config import settings

ALLOWED_EXTENSIONS: dict[str, list[str]] = {
    "application/pdf": [".pdf"],
    "image/jpeg": [".jpg", ".jpeg"],
    "image/png": [".png"],
    "image/gif": [".gif"],
    "image/webp": [".webp"],
    "application/msword": [".doc"],
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
    "application/vnd.ms-excel": [".xls"],
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
    "text/csv": [".csv"],
    "text/plain": [".txt"],
}

ALLOWED_MIME_TYPES: list[str] = list(ALLOWED_EXTENSIONS.keys())


class FileValidationError(Exception):
    pass


class FileValidator:
    @staticmethod
    def validate_size(file_size: int) -> None:
        max_bytes = settings.max_file_size_mb * 1024 * 1024
        if file_size > max_bytes:
            raise FileValidationError(
                f"File size {file_size / 1024 / 1024:.1f}MB exceeds limit of {settings.max_file_size_mb}MB"
            )

    @staticmethod
    def validate_extension(filename: str) -> str:
        ext = Path(filename).suffix.lower()
        allowed_exts = [e for exts in ALLOWED_EXTENSIONS.values() for e in exts]
        if ext not in allowed_exts:
            raise FileValidationError(f"File extension '{ext}' is not allowed")
        return ext

    @staticmethod
    def detect_mime_type(file_data: bytes) -> str:
        import magic
        mime = magic.from_buffer(file_data, mime=True)
        return mime

    @staticmethod
    def validate_mime_type(mime_type: str) -> None:
        if mime_type not in ALLOWED_MIME_TYPES:
            raise FileValidationError(f"MIME type '{mime_type}' is not allowed")


class VirusScanner:
    @staticmethod
    async def scan(file_data: bytes) -> None:
        try:
            import clamav
            result = clamav.scan_buffer(file_data)
            if result and result.get("status") == "FOUND":
                raise FileValidationError(f"Virus detected: {result.get('virus', 'unknown')}")
        except ImportError:
            pass
        except FileValidationError:
            raise
        except Exception:
            pass


def validate_and_prepare_file(file_data: bytes, filename: str) -> tuple[str, str]:
    FileValidator.validate_size(len(file_data))
    ext = FileValidator.validate_extension(filename)
    mime_type = FileValidator.detect_mime_type(file_data)
    FileValidator.validate_mime_type(mime_type)
    return mime_type, ext
