"""
storage/file_storage.py

Persists uploaded documents and submitted report files.

Backend selection:
  - If R2 credentials are configured (Cloudflare R2, or any other
    S3-compatible object storage), files are stored there — durable across
    container restarts/redeploys, unlike Render's free-tier local disk
    (which is wiped on every restart, deploy, or free-tier spin-down).
  - Otherwise, falls back to local disk under the given base_dir, so local
    dev keeps working without needing R2 credentials.

Every reference returned by save_bytes() is a plain string stored directly
in the UploadedFile.file_path / FieldReport.metadata_json["file_path"]
columns — "r2://<key>" for object storage, or a plain filesystem path for
local disk. Every other function in this module accepts either form.
"""

import os
import tempfile
from typing import Optional

R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID", "").strip()
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID", "").strip()
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY", "").strip()
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME", "").strip()

USE_R2 = bool(R2_ACCOUNT_ID and R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY and R2_BUCKET_NAME)

_R2_PREFIX = "r2://"
_client = None


def _get_client():
    global _client
    if _client is None:
        import boto3
        _client = boto3.client(
            "s3",
            endpoint_url=f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
            aws_access_key_id=R2_ACCESS_KEY_ID,
            aws_secret_access_key=R2_SECRET_ACCESS_KEY,
            region_name="auto",
        )
    return _client


def save_bytes(key: str, data: bytes, base_dir: str = "data") -> str:
    """
    Persists `data` under `key`. Returns a storage reference — pass this
    straight into load_bytes/exists/delete/download_to_tempfile later;
    store it as-is in the database.
    """
    if USE_R2:
        _get_client().put_object(Bucket=R2_BUCKET_NAME, Key=key, Body=data)
        return f"{_R2_PREFIX}{key}"

    path = os.path.join(base_dir, key)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    return path


def load_bytes(ref: str) -> bytes:
    """Reads the full contents of a stored file back into memory."""
    if ref.startswith(_R2_PREFIX):
        key = ref[len(_R2_PREFIX):]
        obj = _get_client().get_object(Bucket=R2_BUCKET_NAME, Key=key)
        return obj["Body"].read()
    with open(ref, "rb") as f:
        return f.read()


def exists(ref: Optional[str]) -> bool:
    if not ref:
        return False
    if ref.startswith(_R2_PREFIX):
        key = ref[len(_R2_PREFIX):]
        try:
            _get_client().head_object(Bucket=R2_BUCKET_NAME, Key=key)
            return True
        except Exception:
            return False
    return os.path.exists(ref)


def delete(ref: Optional[str]) -> None:
    if not ref:
        return
    if ref.startswith(_R2_PREFIX):
        key = ref[len(_R2_PREFIX):]
        try:
            _get_client().delete_object(Bucket=R2_BUCKET_NAME, Key=key)
        except Exception:
            pass
    else:
        try:
            os.remove(ref)
        except OSError:
            pass


def download_to_tempfile(ref: str, suffix: str = "") -> str:
    """
    Always returns a path to a freshly-created, disposable temp file
    containing `ref`'s bytes — regardless of whether `ref` is local disk or
    object storage. The caller may unconditionally delete the returned path
    when done; it is never the original permanent copy.

    Used by code that needs a real filesystem path (pytesseract, pdf2image,
    pypdf, python-docx all operate on paths, not byte streams).
    """
    data = load_bytes(ref)
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(data)
        return tmp.name


def is_remote_ref(ref: Optional[str]) -> bool:
    """True if `ref` points at object storage rather than local disk."""
    return bool(ref) and ref.startswith(_R2_PREFIX)
