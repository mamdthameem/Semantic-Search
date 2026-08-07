#Used to delete the pdf vectors from the vectorize.

from vectorize_setup import client, ACCOUNT_ID, INDEX_NAME
from database import get_chunks


def build_vector_ids(pdf_id: str) -> list[str]:
    """Rebuilds vector IDs from the chunks table in SQLite —
    no need to re-download or re-chunk the PDF just to delete."""
    chunks = get_chunks(pdf_id)
    return [f"{pdf_id}_p{c['page_number']}_c{c['chunk_index']}" for c in chunks]


def delete_pdf_vectors(pdf_id: str):
    ids = build_vector_ids(pdf_id)

    # Cloudflare Vectorize limits deletes to 100 IDs at a time
    batch_size = 100
    for i in range(0, len(ids), batch_size):
        batch = ids[i:i + batch_size]
        response = client.vectorize.indexes.delete_by_ids(
            index_name=INDEX_NAME,
            account_id=ACCOUNT_ID,
            ids=batch,
        )
        print(f"Deleted batch of {len(batch)} vectors for pdf_id {pdf_id}. Response: {response}")
        
    print(f"Total {len(ids)} vectors deleted for pdf_id {pdf_id}")


if __name__ == "__main__":
    pdf_id = input("Enter pdf_id to delete: ").strip()
    delete_pdf_vectors(pdf_id)