import os
import tempfile
from storage import download_pdf
from chunking import chunk_pdf
from embeddings import embed_chunks
from vectorize_insert import insert_chunks


def process_pdf(pdf_id: str, source_filename: str):
    """
    Worker function: downloads PDF from MinIO, chunks, embeds, and inserts into Vectorize.
    """
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp_path = tmp.name

    try:
        download_pdf(pdf_id, tmp_path)
        chunks = chunk_pdf(tmp_path)
        chunks = embed_chunks(chunks)
        insert_chunks(chunks, pdf_id, source_filename)
        print(f"\nProcessing complete. pdf_id: {pdf_id}")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

if __name__ == "__main__":
    pdf_id = input("Enter pdf_id to process: ").strip()
    process_pdf(pdf_id, "manual_test.pdf")