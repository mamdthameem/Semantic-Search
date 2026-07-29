#Used to upload and download the pdf to and from the MinIO storage.

from minio import Minio
from minio.error import S3Error
import uuid
import os

from config import (
    MINIO_ENDPOINT,
    MINIO_ACCESS_KEY,
    MINIO_SECRET_KEY,
    MINIO_BUCKET_NAME,
)

BUCKET_NAME = MINIO_BUCKET_NAME

client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False,  # True only if using HTTPS — not needed for local dev
)

def ensure_bucket_exists():             
    if not client.bucket_exists(BUCKET_NAME):
        client.make_bucket(BUCKET_NAME)


def upload_pdf(file_path: str, source_filename: str | None = None) -> str:
    ensure_bucket_exists()
    pdf_id = str(uuid.uuid4())
    object_name = f"{pdf_id}.pdf"
    filename = source_filename or os.path.basename(file_path)

    # Custom metadata — this is how MinIO remembers the ORIGINAL filename,
    # since the object itself is stored under a UUID, not the real name.
    client.fput_object(
        BUCKET_NAME, object_name, file_path,
        metadata={"source-filename": filename},
    )
    return pdf_id


def download_pdf(pdf_id: str, destination_path: str):
    object_name = f"{pdf_id}.pdf"
    client.fget_object(BUCKET_NAME, object_name, destination_path)


def _get_meta(metadata: dict, key: str, default=None):
    """MinIO returns custom metadata keys with varying casing/prefixes
    depending on the SDK version — this looks them up safely either way."""
    target = key.lower()
    for k, v in metadata.items():
        if k.lower().endswith(target):
            return v
    return default


def list_documents() -> list[dict]:
    """
    Lists every PDF currently stored in MinIO — the durable record of
    'previously uploaded documents' your UI needs. MinIO is the single
    source of truth here, not Vectorize (which only knows chunks).
    """
    ensure_bucket_exists()
    documents = []
    for obj in client.list_objects(BUCKET_NAME):
        stat = client.stat_object(BUCKET_NAME, obj.object_name)
        pdf_id = obj.object_name.removesuffix(".pdf")
        filename = _get_meta(stat.metadata or {}, "source-filename", default=obj.object_name)
        documents.append({
            "pdf_id": pdf_id,
            "filename": filename,
            "uploaded_at": stat.last_modified.isoformat() if stat.last_modified else None,
        })
    documents.sort(key=lambda d: d["uploaded_at"] or "", reverse=True)
    return documents