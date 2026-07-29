#Used to query the vectorize for the most relevant chunks to the query.

import requests
from vectorize_setup import ACCOUNT_ID, API_TOKEN, INDEX_NAME
from embeddings import embed_text


def search(query_text: str, top_k: int = 5, pdf_id: str | None = None):
    query_vector = embed_text(query_text)

    url = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/vectorize/v2/indexes/{INDEX_NAME}/query"
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json",
    }

    payload = {
        "vector": query_vector,
        "topK": top_k,
        "returnMetadata": "all",
        "returnValues": False,
    }

    if pdf_id:
        payload["filter"] = {"pdf_id": pdf_id}

    response = requests.post(url, headers=headers, json=payload)
    result = response.json()
    return result


if __name__ == "__main__":
    query = input("Enter your search query: ").strip()
    results = search(query)

    print("\nTop matches:\n")
    matches = results.get("result", {}).get("matches", [])
    for match in matches:
        print(f"Score: {match['score']:.4f}")
        print(f"Page: {match['metadata']['page_number']} | Chunk: {match['metadata']['chunk_index']}")
        print(f"Char range: {match['metadata']['char_start']}-{match['metadata']['char_end']}")
        print("-" * 60)