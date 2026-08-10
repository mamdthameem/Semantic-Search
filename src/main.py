#Used to serve the frontend and the api.

import os
import shutil
import tempfile

import uvicorn
from fastapi import FastAPI, UploadFile, File
from fastapi.staticfiles import StaticFiles

import pika
import json
from vectorize_query import search
from storage import list_documents, delete_document, upload_pdf
from vectorize_delete import delete_pdf_vectors
from database import create_task, list_tasks, delete_task, delete_chunks
from rag import answer_question

app = FastAPI(title="Semantic PDF Search")


@app.post("/upload")
async def upload_endpoint(file: UploadFile = File(...)):
    # Receives a PDF from the browser, saves it to MinIO, creates a status row, and enqueues the task.
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        # 1. Upload to MinIO
        pdf_id = upload_pdf(tmp_path, source_filename=file.filename)
        
        # 2. Track in SQLite
        create_task(pdf_id, file.filename)
        
        # 3. Publish to RabbitMQ
        connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
        channel = connection.channel()
        
        args = {
            'x-dead-letter-exchange': '',
            'x-dead-letter-routing-key': 'pdf_tasks_dlq'
        }
        channel.queue_declare(queue='pdf_tasks', durable=True, arguments=args)
        
        message = json.dumps({"pdf_id": pdf_id})
        channel.basic_publish(
            exchange='',
            routing_key='pdf_tasks',
            body=message,
            properties=pika.BasicProperties(
                delivery_mode=pika.spec.PERSISTENT_DELIVERY_MODE
            )
        )
        connection.close()
    finally:
        os.remove(tmp_path)

    return {"pdf_id": pdf_id, "filename": file.filename, "status": "UPLOADED"}

@app.get("/documents")
def list_documents_endpoint():
    return {"documents": list_tasks()}


@app.delete("/documents/{pdf_id}")
def delete_document_endpoint(pdf_id: str):
    # 1. Delete vectors from Vectorize. IDs are rebuilt from the chunks table
    #    in SQLite, so we no longer need to download/re-chunk the PDF here.
    try:
        delete_pdf_vectors(pdf_id)
    except Exception as e:
        print(f"Warning: Failed to delete vectors (maybe already deleted?): {e}")

    # 2. Delete from MinIO
    try:
        delete_document(pdf_id)
    except Exception as e:
        return {"error": f"Failed to delete from MinIO: {e}"}

    # 3. Delete from SQLite (task row + the chunk tracking rows)
    try:
        delete_task(pdf_id)
        delete_chunks(pdf_id)
    except Exception as e:
        print(f"Warning: Failed to delete task from DB: {e}")

    return {"status": "success", "pdf_id": pdf_id}


@app.get("/search")
def search_endpoint(query: str, top_k: int = 3, pdf_id: str | None = None):
    # Runs the query through Vectorize and returns each match's text straight
    # from the vector metadata — no MinIO round trip. char_start/char_end are
    # still returned for the future "highlight inside the PDF" feature.
    raw_results = search(query, top_k=top_k, pdf_id=pdf_id)
    matches = raw_results.get("result", {}).get("matches", [])

    enriched = []
    for match in matches:
        meta = match["metadata"]
        enriched.append({
            "score": match["score"],
            "pdf_id": meta["pdf_id"],
            "source_filename": meta.get("source_filename", "unknown.pdf"),
            "page_number": meta["page_number"],
            "char_start": meta["char_start"],
            "char_end": meta["char_end"],
            "highlighted_text": meta.get("text", ""),
        })

    return {"query": query, "results": enriched}


@app.get("/ask")
def ask_endpoint(question: str, pdf_id: str | None = None):
    # RAG endpoint: hands the question to the local LLM, which calls the
    # search_documents tool to retrieve chunks and writes a grounded answer.
    # pdf_id (the library selection) scopes the search, same as /search.
    result = answer_question(question, pdf_id=pdf_id)
    return {
        "question": question,
        "answer": result["answer"],
        "sources": result["sources"],
    }


# Serve the frontend — path built from this file's own location, so it
# works no matter what folder you launch the script from.
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="frontend")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)