#Used to ingest the pdf into the vectorize. (WHOLE PIPELINE)

import os
from storage import upload_pdf
from chunking import chunk_pdf
from embeddings import embed_chunks
from vectorize_insert import insert_chunks


def ingest_pdf(pdf_path: str, source_filename: str | None = None) -> str: #Full pipeline: upload PDF to MinIO, then chunk + embed + insert into Vectorize — all tagged with the SAME pdf_id.
    pdf_id = upload_pdf(pdf_path)
    chunks = chunk_pdf(pdf_path)
    chunks = embed_chunks(chunks)
    insert_chunks(chunks, pdf_id, source_filename or os.path.basename(pdf_path))
    print(f"\nIngestion complete. pdf_id: {pdf_id}")
    return pdf_id


if __name__ == "__main__":
    pdf_path = input("Enter path to a PDF file: ").strip()
    ingest_pdf(pdf_path)