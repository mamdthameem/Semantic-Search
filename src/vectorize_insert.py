#Used to insert the chunks into the vectorize.

import json
import requests
from vectorize_setup import ACCOUNT_ID, API_TOKEN, INDEX_NAME


def chunks_to_ndjson(chunks: list[dict], pdf_id: str, source_filename: str) -> bytes:
    lines = []
    for chunk in chunks:
        vector_id = f"{pdf_id}_p{chunk['page_number']}_c{chunk['chunk_index']}"

        metadata = {
            "pdf_id": pdf_id,
            "source_filename": source_filename,
            "page_number": chunk["page_number"],
            "chunk_index": chunk["chunk_index"],
            "char_start": chunk["core_char_start"],
            "char_end": chunk["core_char_end"],
            "word_count": chunk["word_count"],
            # The full chunk text (overlap prefix included) so search can display
            # it straight from Vectorize, no MinIO round trip. char_start/char_end
            # above stay for the future "highlight inside the PDF" feature.
            "text": chunk["text"],
        }

        line = json.dumps({
            "id": vector_id,
            "values": chunk["embedding"],
            "metadata": metadata,
        })
        lines.append(line)

    return "\n".join(lines).encode("utf-8")


def insert_chunks(chunks: list[dict], pdf_id: str, source_filename: str):
    ndjson_body = chunks_to_ndjson(chunks, pdf_id, source_filename)

    url = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/vectorize/v2/indexes/{INDEX_NAME}/insert"
    headers = {"Authorization": f"Bearer {API_TOKEN}"}

    response = requests.post(url, headers=headers, files={"vectors": ndjson_body})
    result = response.json()
    print("Status:", response.status_code)
    print("Response:", result)
    return result


if __name__ == "__main__":
    import uuid
    from chunking import chunk_pdf
    from embeddings import embed_chunks

    pdf_path = input("Enter path to a PDF file: ").strip()
    pdf_id = str(uuid.uuid4())

    chunks = chunk_pdf(pdf_path)
    chunks = embed_chunks(chunks)
    insert_chunks(chunks, pdf_id)

    print(f"\nInserted {len(chunks)} chunks under pdf_id: {pdf_id}")