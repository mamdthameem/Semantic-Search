#Used to extract text blocks from a digital PDF, page by page. and also to rebuild the page text from the blocks

import fitz  # PyMuPDF

def extract_pdf(pdf_path: str) -> list[dict]: #extracts text blocks from a digital PDF, page by page
    doc = fitz.open(pdf_path) #open the pdf file
    extracted_blocks = []

    for page_number, page in enumerate(doc, start=1):
        blocks = page.get_text("blocks")  # returns list of tuples page by page

        for block_index, block in enumerate(blocks):
            x0, y0, x1, y1, text, block_no, block_type = block #Bounding box coordinates for the block

            text = text.strip()
            if not text:  # skip empty blocks (images, whitespace regions)
                continue

            extracted_blocks.append({ #returns a clean list
                "page_number": page_number,
                "block_index": block_index,
                "text": text,
                "bbox": [x0, y0, x1, y1],
            })

    doc.close()
    return extracted_blocks

def build_page_text_from_blocks(blocks: list[dict]) -> str: #rebuilds the page text from the blocks
    """
    The SINGLE source of truth for how page text is reconstructed from blocks.
    Both chunking.py and retrieval.py must use this exact function —
    never reimplement this joining logic separately.
    """
    texts = [b["text"].strip() for b in blocks if b["text"].strip()]
    return "\n\n".join(texts)


if __name__ == "__main__": #standalone to execute extraction of pdf in this file alone
    pdf_path = input("Enter path to a PDF file: ").strip()
    results = extract_pdf(pdf_path)

    print(f"\nExtracted {len(results)} blocks from {pdf_path}\n")
    for block in results[:5]:  # just show first 5 to sanity-check
        print(f"Page {block['page_number']} | Block {block['block_index']}")
        print(f"BBox: {block['bbox']}")
        print(f"Text: {block['text'][:150]}...")  # truncate long text for readability