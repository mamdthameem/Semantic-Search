#Used to create the index and metadata indexes for the vectorize. (Setup file for the vectorize)

from cloudflare import Cloudflare

from config import CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN, VECTORIZE_INDEX_NAME

ACCOUNT_ID = CLOUDFLARE_ACCOUNT_ID
API_TOKEN = CLOUDFLARE_API_TOKEN
INDEX_NAME = VECTORIZE_INDEX_NAME

client = Cloudflare(api_token=API_TOKEN)


def create_index():
    response = client.vectorize.indexes.create(
        account_id=ACCOUNT_ID,
        name=INDEX_NAME,
        config={"dimensions": 384, "metric": "cosine"},
        description="Semantic search pipeline - PDF chunk embeddings",
    )
    print("Index created:", response)


def create_metadata_indexes():
    """
    Vectorize requires you to explicitly declare which metadata fields
    are filterable BEFORE inserting any vectors — max 10 fields.
    We only need pdf_id, page_number, and chunk_index to be filterable;
    other metadata (char_start, char_end, word_count) is still stored
    and retrievable, just not used as a filter condition.
    """
    fields = [
        ("pdf_id", "string"),
        ("page_number", "number"),
        ("chunk_index", "number"),
    ]
    for property_name, index_type in fields:
        response = client.vectorize.indexes.metadata_index.create(
            index_name=INDEX_NAME,
            account_id=ACCOUNT_ID,
            property_name=property_name,
            index_type=index_type,
        )
        print(f"Metadata index created for '{property_name}':", response)

def verify_index():
    response = client.vectorize.indexes.get(
        index_name=INDEX_NAME,
        account_id=ACCOUNT_ID,
    )
    print("Index details:", response)

    metadata_indexes = client.vectorize.indexes.metadata_index.list(
        index_name=INDEX_NAME,
        account_id=ACCOUNT_ID,
    )
    print("Metadata indexes:", metadata_indexes)


if __name__ == "__main__":
    create_index()
    create_metadata_indexes()
    verify_index()