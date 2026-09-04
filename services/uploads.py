"""Validated public and private upload handling."""

import mimetypes
import uuid
from pathlib import Path

from flask import current_app
from werkzeug.utils import secure_filename


ALLOWED = {
    "profile": {"png", "jpg", "jpeg", "webp"},
    "identity": {"png", "jpg", "jpeg", "pdf"},
    "certificate": {"png", "jpg", "jpeg", "pdf"},
    "evidence_image": {"png", "jpg", "jpeg", "webp"},
    "evidence_video": {"mp4", "webm", "mov"},
    "product": {"png", "jpg", "jpeg", "webp"},
}


def save_upload(file_storage, category):
    if not file_storage or not file_storage.filename:
        return None
    if category not in ALLOWED:
        raise ValueError("Unsupported upload category.")
    original = secure_filename(file_storage.filename)
    if not original or "." not in original:
        raise ValueError("Please upload a file with a supported extension.")
    extension = original.rsplit(".", 1)[1].lower()
    if extension not in ALLOWED[category]:
        raise ValueError("This file type is not allowed for the selected document.")
    declared_type = (file_storage.mimetype or "").lower()
    if declared_type and declared_type not in {"application/octet-stream", "application/pdf", "image/png", "image/jpeg", "image/webp", "video/mp4", "video/webm", "video/quicktime"}:
        raise ValueError("The uploaded MIME type is not supported.")
    content_length = int(file_storage.content_length or 0)
    if content_length > current_app.config["MAX_CONTENT_LENGTH"]:
        raise ValueError("This file is larger than the allowed upload size.")
    stored = f"{uuid.uuid4().hex}.{extension}"
    if category in {"profile", "product"}:
        destination = Path(current_app.config["PUBLIC_UPLOAD_FOLDER"])
    else:
        destination = Path(current_app.config["PRIVATE_UPLOAD_FOLDER"])
    destination.mkdir(parents=True, exist_ok=True)
    file_storage.save(destination / stored)
    size = (destination / stored).stat().st_size
    if size > current_app.config["MAX_CONTENT_LENGTH"]:
        (destination / stored).unlink(missing_ok=True)
        raise ValueError("This file is larger than the allowed upload size.")
    return {
        "original_name": original,
        "stored_name": stored,
        "mime_type": mimetypes.guess_type(original)[0] or "application/octet-stream",
        "size_bytes": size,
    }
