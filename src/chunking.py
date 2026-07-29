#Used to chunk the pdf blocks into chunks, by grouping the blocks into word-capped chunks with sentence fallback and overlap.

import re
from extraction import extract_pdf

MAX_CHUNK_WORDS = 100
OVERLAP_WORDS = int(MAX_CHUNK_WORDS * 0.10)  # ~10 words


def split_into_sentences(text: str) -> list[str]: #Naive punctuation-based sentence splitter. Works well on clean digital PDF text.
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s for s in sentences if s]

def build_page_text(blocks: list[dict]) -> list[dict]: #for group_blocks_into_chunks function 
    """
    Reconstructs a page's full text by joining its blocks with "\n\n",
    and records each block's exact [start, end) offset within that
    reconstructed text. Returns a LIST OF DICTS — not a string.
    """
    block_spans = []
    cursor = 0
    for block in blocks:
        text = block["text"]
        start = cursor
        end = start + len(text)
        block_spans.append({**block, "page_char_start": start, "page_char_end": end})
        cursor = end + 2  # +2 for "\n\n" separator
    return block_spans

def group_blocks_into_chunks(blocks: list[dict], page_number: int) -> list[dict]: #Groups one page's blocks into word-capped chunks with sentence fallback and overlap.
    block_spans = build_page_text(blocks)

    chunks = []
    chunk_index = 0
    current_blocks = []
    current_word_count = 0
    previous_chunk_tail_words: list[str] = []

    def finalize_chunk():
        nonlocal chunk_index, current_blocks, current_word_count, previous_chunk_tail_words
        if not current_blocks:
            return
        core_text = " ".join(b["text"] for b in current_blocks)
        overlap_prefix = " ".join(previous_chunk_tail_words)
        full_text = (overlap_prefix + " " + core_text).strip() if overlap_prefix else core_text

        chunks.append({
            "page_number": page_number,
            "chunk_index": chunk_index,
            "text": full_text,
            "core_char_start": current_blocks[0]["page_char_start"],
            "core_char_end": current_blocks[-1]["page_char_end"],
            "word_count": len(full_text.split()),
            "bboxes": [b["bbox"] for b in current_blocks],
        })

        core_words = core_text.split()
        previous_chunk_tail_words = core_words[-OVERLAP_WORDS:] if core_words else []
        chunk_index += 1
        current_blocks = []
        current_word_count = 0

    for block in block_spans:
        block_word_count = len(block["text"].split())

        if block_word_count > MAX_CHUNK_WORDS:
            sentences = split_into_sentences(block["text"])
            cursor = block["page_char_start"]
            for sentence in sentences:
                sentence_words = len(sentence.split())
                if current_word_count + sentence_words > MAX_CHUNK_WORDS:
                    finalize_chunk()
                sentence_start = cursor
                sentence_end = sentence_start + len(sentence)
                current_blocks.append({
                    "text": sentence,
                    "page_char_start": sentence_start,
                    "page_char_end": sentence_end,
                    "bbox": block["bbox"],
                })
                current_word_count += sentence_words
                cursor = sentence_end + 1
            continue

        if current_word_count + block_word_count > MAX_CHUNK_WORDS:
            finalize_chunk()

        current_blocks.append(block)
        current_word_count += block_word_count

    finalize_chunk()
    return chunks


def chunk_pdf(pdf_path: str) -> list[dict]:
    blocks = extract_pdf(pdf_path)
    pages: dict[int, list[dict]] = {}
    for block in blocks:
        pages.setdefault(block["page_number"], []).append(block)

    all_chunks = []
    for page_number, page_blocks in sorted(pages.items()):
        all_chunks.extend(group_blocks_into_chunks(page_blocks, page_number))
    return all_chunks


if __name__ == "__main__": #standalone to execute chunking of pdf in this file alone
    pdf_path = input("Enter path to a PDF file: ").strip()
    results = chunk_pdf(pdf_path)

    print(f"\nGenerated {len(results)} chunks from {pdf_path}\n")
    for chunk in results:
        print(f"Page {chunk['page_number']} | Chunk {chunk['chunk_index']} | {chunk['word_count']} words")
        print(f"Core char range: {chunk['core_char_start']}-{chunk['core_char_end']}")
        print(f"Text: {chunk['text'][:200]}...")
        print("-" * 60)