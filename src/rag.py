# RAG via tool calling.

import ollama

from config import OLLAMA_MODEL
from vectorize_query import search

# How many times we let the model call a tool before we force it to answer.
# A guard against an accidental infinite "search again, search again" loop.
MAX_TOOL_ROUNDS = 3

# How many chunks each search pulls back for the model to read.
SEARCH_TOP_K = 5


# The tool definition. This is just data — a JSON schema the model reads to
# learn what the tool is called and what arguments it takes. We write it by hand
# (rather than letting the ollama package infer it from a Python function) so the
# shape is fully visible: a "function" with a name, a description the model uses
# to decide WHEN to call it, and a typed list of parameters.
SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "search_documents",
        "description": (
            "Search the user's uploaded PDF library for passages relevant to a "
            "query. Returns the most relevant text chunks, each labelled with its "
            "source filename and page number. Call this whenever you need facts "
            "from the documents to answer the user."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "A natural-language phrase describing what to look for, "
                        "e.g. 'the refund policy' or 'author's main argument'."
                    ),
                },
            },
            "required": ["query"],
        },
    },
}


# The system prompt sets the model's job.
SYSTEM_PROMPT = (
    "You are a helpful assistant that answers questions about the user's "
    "uploaded PDF documents. To find information, call the search_documents "
    "tool — do not answer from your own prior knowledge. Base your answer only "
    "on the passages the tool returns, and mention the page number(s) you used. "
    "If the passages do not contain the answer, say you could not find it in the "
    "documents."
)


def run_search_tool(query: str, pdf_id: str | None, sources: list) -> str:
 #the tool used to search chunks from Vectorize for the input of the model
    raw_results = search(query, top_k=SEARCH_TOP_K, pdf_id=pdf_id)
    matches = raw_results.get("result", {}).get("matches", [])

    if not matches:
        return "No relevant passages were found in the documents."

    blocks = []
    for match in matches:
        meta = match["metadata"]
        filename = meta.get("source_filename", "unknown.pdf")
        page_number = meta["page_number"]
        text = meta.get("text", "")

        # Human-readable block the model reads. The [filename, page N] header is
        # what lets the model cite pages in its answer.
        blocks.append(f"[{filename}, page {page_number}]\n{text}")

        # Structured record for the UI's "Sources" list at end.
        sources.append({
            "score": match["score"],
            "source_filename": filename,
            "page_number": page_number,
            "text": text,
        })

    return "\n\n---\n\n".join(blocks)


def answer_question(question: str, pdf_id: str | None = None) -> dict:
    """
    Run the full tool-calling loop for one question and return the answer.

    Returns {"answer": str, "sources": [ ... ]}.
    """
    # The running conversation. We start with the rules + the user's question,
    # and append each turn (assistant tool-calls, our tool results) as we go so
    # the model always sees the full history.
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]

    # Filled in by run_search_tool each time the model searches.
    sources = []

    for _ in range(MAX_TOOL_ROUNDS):
        # Send the conversation + the tool description to the model.
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=messages,
            tools=[SEARCH_TOOL],
        )
        assistant_message = response.message

        # Keep the assistant's turn in the history (it holds the tool_calls).
        messages.append(assistant_message)

        tool_calls = assistant_message.tool_calls
        if not tool_calls:
            # No tool call means the model is done and wrote a plain answer.
            return {"answer": assistant_message.content or "", "sources": sources}

        # The model asked to call one or more tools. Run each, and feed the
        # result back as a "tool" message the model will read next round.
        for call in tool_calls:
            if call.function.name == "search_documents":
                query = call.function.arguments.get("query", "")
                result_text = run_search_tool(query, pdf_id, sources)
            else:
                # The model invented a tool we don't have — tell it so.
                result_text = f"Unknown tool: {call.function.name}"

            messages.append({
                "role": "tool",
                "tool_name": call.function.name,
                "content": result_text,
            })

    # We ran out of rounds while the model was still calling tools. Make one
    # final call WITHOUT tools so it's forced to write an answer from what it has.
    final = ollama.chat(model=OLLAMA_MODEL, messages=messages)
    return {"answer": final.message.content or "", "sources": sources}


if __name__ == "__main__":
    # Standalone manual test — no web server needed. Ask a question about a PDF
    # you've already uploaded/indexed and see the grounded answer + its sources.
    question = input("Enter your question: ").strip()
    result = answer_question(question)

    print("\nAnswer:\n")
    print(result["answer"])

    print("\nSources used:\n")
    for source in result["sources"]:
        print(f"- {source['source_filename']} (page {source['page_number']}, score {source['score']:.3f})")
