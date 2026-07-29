#Used to upload and download the pdf to and from the MinIO storage.

from minio import Minio
from minio.error import S3Error
import uuid
import io

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
    """Creates the bucket if it doesn't already exist. Safe to call every time."""
    if not client.bucket_exists(BUCKET_NAME):
        client.make_bucket(BUCKET_NAME)
        print(f"Created bucket: {BUCKET_NAME}")


def upload_pdf(file_path: str, source_filename: str | None = None) -> str:
    """
    Uploads a PDF to MinIO and returns a unique pdf_id —
    this ID is what Vectorize metadata will reference later.
    """
    ensure_bucket_exists()
    pdf_id = str(uuid.uuid4())
    object_name = f"{pdf_id}.pdf"

    client.fput_object(BUCKET_NAME, object_name, file_path)
    print(f"Uploaded {file_path} as {object_name}")
    return pdf_id


def download_pdf(pdf_id: str, destination_path: str):
    """Downloads a PDF back from MinIO using its pdf_id."""
    object_name = f"{pdf_id}.pdf"
    client.fget_object(BUCKET_NAME, object_name, destination_path)
    print(f"Downloaded {object_name} to {destination_path}")


if __name__ == "__main__":
    test_path = input("Enter path to a PDF to upload: ").strip()
    pdf_id = upload_pdf(test_path)
    print(f"\npdf_id: {pdf_id}")

    download_pdf(pdf_id, "downloaded_test.pdf")