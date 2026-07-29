#Used to embed the chunks into a 384-dimensional embedding vector.

from sentence_transformers import SentenceTransformer

MODEL_NAME = "all-MiniLM-L6-v2"

_model = SentenceTransformer(MODEL_NAME)


def embed_text(text: str) -> list[float]: #Converts a single string into a 384-dimensional embedding vector.

    embedding = _model.encode(text, normalize_embeddings=True)
    return embedding.tolist()


def embed_chunks(chunks: list[dict]) -> list[dict]: #Takes chunking.py's output (list of chunk dicts) and adds an "embedding" key to each one, in place.
    for chunk in chunks:
        chunk["embedding"] = embed_text(chunk["text"])
    return chunks


if __name__ == "__main__":
    from chunking import chunk_pdf

    pdf_path = input("Enter path to a PDF file: ").strip()
    chunks = chunk_pdf(pdf_path)
    chunks = embed_chunks(chunks) #Takes chunking.py's output (list of chunk dicts) and adds an "embedding" key to each one, in place.

    print(f"\nEmbedded {len(chunks)} chunks\n")
    for chunk in chunks[:3]:  # just first 3 to sanity-check the embedding
        print(f"Page {chunk['page_number']} | Chunk {chunk['chunk_index']}")
        print(f"Embedding length: {len(chunk['embedding'])}")
        print(f"First 5 values: {chunk['embedding'][:5]}")
        print("-" * 60)