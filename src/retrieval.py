import fitz
from storage import client as minio_client, BUCKET_NAME
from extraction import build_page_text_from_blocks

def get_pdf_bytes(pdf_id: str) -> bytes:
    """Fetches raw PDF bytes from MinIO — kept in memory, never written to disk."""
    object_name = f"{pdf_id}.pdf"
    response = minio_client.get_object(BUCKET_NAME, object_name)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def get_page_text(pdf_id: str, page_number: int) -> str:
    """
    Fetches the real page text, rebuilt EXACTLY the way chunking.py's
    build_page_text() did — same block order, same '\\n\\n' join — so stored
    char_start/char_end offsets line up correctly against this reconstruction.
    """
    pdf_bytes = get_pdf_bytes(pdf_id)
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[page_number - 1]

    blocks = page.get_text("blocks")
    block_dicts = [{"text": b[4]} for b in blocks]
    page_text = build_page_text_from_blocks(block_dicts)

    doc.close()
    return page_text


def get_highlighted_chunk(pdf_id: str, page_number: int, char_start: int, char_end: int) -> dict:
    """Fetches the real page text and slices out the exact matched chunk."""
    page_text = get_page_text(pdf_id, page_number)
    return {
        "full_page_text": page_text,
        "highlighted_text": page_text[char_start:char_end],
        "char_start": char_start,
        "char_end": char_end,
    }


if __name__ == "__main__":
    pdf_id = input("Enter pdf_id: ").strip()
    page_number = int(input("Enter page number: ").strip())
    char_start = int(input("Enter char_start: ").strip())
    char_end = int(input("Enter char_end: ").strip())

    result = get_highlighted_chunk(pdf_id, page_number, char_start, char_end)
    print("\nHighlighted text:\n")
    print(result["highlighted_text"])