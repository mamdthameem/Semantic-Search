#Used to delete the pdf vectors from the vectorize.

from vectorize_setup import client, ACCOUNT_ID, INDEX_NAME
from chunking import chunk_pdf


def build_vector_ids(pdf_path: str, pdf_id: str) -> list[str]:
    """Regenerates vector IDs deterministically — no need to re-embed just to delete."""
    chunks = chunk_pdf(pdf_path)
    return [f"{pdf_id}_p{c['page_number']}_c{c['chunk_index']}" for c in chunks]


def delete_pdf_vectors(pdf_path: str, pdf_id: str):
    ids = build_vector_ids(pdf_path, pdf_id)
    response = client.vectorize.indexes.delete_by_ids(
        index_name=INDEX_NAME,
        account_id=ACCOUNT_ID,
        ids=ids,
    )
    print(f"Deleted {len(ids)} vectors for pdf_id {pdf_id}")
    print("Response:", response)


if __name__ == "__main__":
    pdf_path = input("Enter path to the original PDF: ").strip()
    pdf_id = input("Enter pdf_id to delete: ").strip()
    delete_pdf_vectors(pdf_path, pdf_id)