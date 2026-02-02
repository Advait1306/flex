from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Any
from pathlib import Path
import uuid
import json

app = FastAPI()

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
def save_document(doc_id: str, body: DocumentContent):
    """Save document content"""
    data = load_data()
    data["documents"][doc_id] = body.content
    if doc_id not in data["order"]:
        data["order"].append(doc_id)
    save_data(data)
    return {"status": "saved"}


@app.delete("/api/documents/{doc_id}")
def delete_document(doc_id: str):
    """Delete a document"""
    data = load_data()
    data["documents"].pop(doc_id, None)
    if doc_id in data["order"]:
        data["order"].remove(doc_id)
    save_data(data)
    return {"status": "deleted"}
