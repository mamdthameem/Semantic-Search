#Used to serve the frontend and the api.

import os
import shutil
import tempfile

import uvicorn
from fastapi import FastAPI, UploadFile, File
from fastapi.staticfiles import StaticFiles

from ingest import ingest_pdf
from vectorize_query import search
from retrieval import get_highlighted_chunk
from storage import list_documents, download_pdf, delete_document
from vectorize_delete import delete_pdf_vectors

app = FastAPI(title="Semantic PDF Search")


@app.post("/upload")
async def upload_endpoint(file: UploadFile = File(...)):
    #Receives a PDF from the browser, saves it to a temp path (ingest_pdf and MinIO both expect a real file path, not raw upload bytes), runs the full ingestion pipeline, then cleans up the temp file.
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        pdf_id = ingest_pdf(tmp_path, source_filename=file.filename)
    finally:
        os.remove(tmp_path)

    return {"pdf_id": pdf_id, "filename": file.filename}

@app.get("/documents")
def list_documents_endpoint():
    return {"documents": list_documents()}


@app.delete("/documents/{pdf_id}")
def delete_document_endpoint(pdf_id: str):
    # 1. Download the PDF from MinIO to a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp_path = tmp.name

    try:
        download_pdf(pdf_id, tmp_path)
    except Exception as e:
        os.remove(tmp_path)
        return {"error": f"Document not found or error downloading: {e}"}

    # 2. Delete vectors from Vectorize (needs the PDF to calculate chunk IDs)
    try:
        delete_pdf_vectors(tmp_path, pdf_id)
    except Exception as e:
        print(f"Warning: Failed to delete vectors (maybe already deleted?): {e}")
    finally:
        os.remove(tmp_path)

    # 3. Delete from MinIO
    try:
        delete_document(pdf_id)
    except Exception as e:
        return {"error": f"Failed to delete from MinIO: {e}"}
        
    return {"status": "success", "pdf_id": pdf_id}


@app.get("/search")
def search_endpoint(query: str, top_k: int = 5, pdf_id: str | None = None):
    #Runs the query through Vectorize, then for each match, fetches the real text back from MinIO via retrieval.py — this is the "pointer index → real content" mechanism you already understand.
    raw_results = search(query, top_k=top_k, pdf_id=pdf_id)
    matches = raw_results.get("result", {}).get("matches", [])

    enriched = []
    for match in matches:
        meta = match["metadata"]
        highlight = get_highlighted_chunk(
            pdf_id=meta["pdf_id"],
            page_number=meta["page_number"],
            char_start=meta["char_start"],
            char_end=meta["char_end"],
        )
        enriched.append({
            "score": match["score"],
            "pdf_id": meta["pdf_id"],
            "source_filename": meta.get("source_filename", "unknown.pdf"),
            "page_number": meta["page_number"],
            "char_start": meta["char_start"],
            "char_end": meta["char_end"],
            "highlighted_text": highlight["highlighted_text"],
            "full_page_text": highlight["full_page_text"],
        })

    return {"query": query, "results": enriched}


# Serve the frontend — path built from this file's own location, so it
# works no matter what folder you launch the script from.
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="frontend")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)