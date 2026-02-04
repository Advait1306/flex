import json
import uuid
from pathlib import Path
from typing import Any, List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agents.queue_manager import get_queue_manager
from routers import pipeline_router

app = FastAPI()

# Include routers
app.include_router(pipeline_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# File-based storage
STORAGE_DIR = Path(__file__).parent.parent / "storage"
STORAGE_DIR.mkdir(exist_ok=True)
DOCUMENTS_FILE = STORAGE_DIR / "documents.json"


def load_data() -> dict:
    if DOCUMENTS_FILE.exists():
        with open(DOCUMENTS_FILE, "r") as f:
            return json.load(f)
    return {"documents": {}, "order": []}


def save_data(data: dict):
    with open(DOCUMENTS_FILE, "w") as f:
        json.dump(data, f, indent=2)


class DocumentContent(BaseModel):
    content: List[Any]


def extract_text_from_blocks(blocks: List[Any]) -> str:
    """Extract all text content from BlockNote blocks"""
    texts = []
    for block in blocks:
        if isinstance(block, dict) and "content" in block:
            content = block["content"]
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and "text" in item:
                        texts.append(item["text"])
        # Handle nested children blocks
        if isinstance(block, dict) and "children" in block:
            texts.append(extract_text_from_blocks(block["children"]))
    return "".join(texts)


def truncate_to_last_n_words(text: str, max_words: int = 10000) -> str:
    """Truncate text to the last N words."""
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[-max_words:])


@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI"}


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


@app.get("/api/documents")
def list_documents():
    """Get all documents in order"""
    data = load_data()
    return {
        "documents": [
            {"id": doc_id, "content": data["documents"].get(doc_id, [])}
            for doc_id in data["order"]
        ]
    }


@app.post("/api/documents")
def create_document():
    """Create a new document"""
    data = load_data()
    doc_id = str(uuid.uuid4())
    data["documents"][doc_id] = []
    data["order"].append(doc_id)
    save_data(data)
    return {"id": doc_id}


@app.put("/api/documents/{doc_id}")
async def save_document(doc_id: str, body: DocumentContent):
    """Save document content and trigger pipeline on new content."""
    data = load_data()

    # Get old content and extract text
    old_content = data["documents"].get(doc_id, [])
    old_text = extract_text_from_blocks(old_content)

    # Extract text from new content
    new_text = extract_text_from_blocks(body.content)

    # Find the new/changed text and queue pipeline trigger
    trigger_text = None
    if new_text.startswith(old_text):
        diff = new_text[len(old_text):]
        if diff.strip():
            trigger_text = diff.strip()
            print(f"[NEW] {trigger_text}")
    elif new_text != old_text:
        # Content changed in a non-append way - use full new text as trigger
        trigger_text = new_text.strip()
        print(f"[CHANGED] {trigger_text}")

    # Save document first
    data["documents"][doc_id] = body.content
    if doc_id not in data["order"]:
        data["order"].append(doc_id)
    save_data(data)

    # Queue pipeline trigger if there's new content
    if trigger_text:
        # Extract and truncate document context for the pipeline
        full_doc_text = extract_text_from_blocks(body.content)
        doc_context = truncate_to_last_n_words(full_doc_text, max_words=10000)

        queue_manager = get_queue_manager()
        await queue_manager.enqueue(
            trigger=trigger_text,
            document_id=doc_id,
            document_context=doc_context,
        )
        status = queue_manager.get_status()
        return {
            "status": "saved",
            "pipeline_queued": True,
            "queue_size": status["queue_size"],
        }

    return {"status": "saved", "pipeline_queued": False}


@app.delete("/api/documents/{doc_id}")
def delete_document(doc_id: str):
    """Delete a document"""
    data = load_data()
    data["documents"].pop(doc_id, None)
    if doc_id in data["order"]:
        data["order"].remove(doc_id)
    save_data(data)
    return {"status": "deleted"}


@app.get("/api/pipeline/status")
def get_pipeline_status():
    """Get the current pipeline queue status."""
    queue_manager = get_queue_manager()
    return queue_manager.get_status()


@app.get("/api/pipeline/result/{doc_id}")
def get_pipeline_result(doc_id: str):
    """Get the last pipeline result for a document."""
    queue_manager = get_queue_manager()
    result = queue_manager.get_last_result(doc_id)
    if result is None:
        return {"status": "no_result", "document_id": doc_id}
    return {"status": "ok", "document_id": doc_id, "result": result}
