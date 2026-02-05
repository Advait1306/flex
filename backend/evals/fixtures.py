import json
import uuid
from pathlib import Path

import yaml
from qdrant_client.models import (
    Distance,
    MultiVectorComparator,
    MultiVectorConfig,
    PointStruct,
    TextIndexParams,
    TextIndexType,
    TokenizerType,
    VectorParams,
)

from store.embeddings import get_embeddings
from store.qdrant import EMBEDDING_DIM, get_client

_EVAL_NAMESPACE = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")

def fixture_id(short_id: str) -> str:
    """Convert a short fixture ID (e.g. 't1') to a deterministic UUID string.

    Qdrant requires UUIDs or unsigned ints for point IDs. This lets YAML files
    use readable short IDs while producing valid Qdrant IDs.
    """
    return str(uuid.uuid5(_EVAL_NAMESPACE, short_id))


TODOS_EVAL_COLLECTION = "todos_eval"
FACTS_EVAL_COLLECTION = "facts_eval"
FIXTURES_DIR = Path(__file__).parent / "datasets" / "fixtures"
FIXTURE_DATA_DIR = Path(__file__).parent / "fixture_data"


def generate_fixtures():
    """Compute embeddings for all fixture YAML files, write JSON per fixture."""
    for yaml_path in sorted(FIXTURES_DIR.glob("*.yaml")):
        name = yaml_path.stem
        with open(yaml_path) as f:
            fixtures = yaml.safe_load(f)

        out_dir = FIXTURE_DATA_DIR / name
        out_dir.mkdir(parents=True, exist_ok=True)

        # --- Todos ---
        todo_points = []
        for todo in fixtures.get("todos", []):
            if todo.get("tags"):
                texts_to_embed = todo["tags"]
            else:
                texts_to_embed = [todo["title"]]
                if todo.get("description"):
                    texts_to_embed.append(todo["description"])

            embeddings = get_embeddings(texts_to_embed)

            payload = {
                "title": todo["title"],
                "status": todo["status"],
            }
            if todo.get("description"):
                payload["description"] = todo["description"]
            if todo.get("tags"):
                payload["tags"] = todo["tags"]

            todo_points.append({
                "id": todo["id"],
                "vector": embeddings,
                "payload": payload,
            })

        with open(out_dir / "todos.json", "w") as f:
            json.dump(todo_points, f, indent=2)

        # --- Facts ---
        fact_points = []
        for fact in fixtures.get("facts", []):
            texts_to_embed = fact.get("tags") or [fact["fact"]]
            embeddings = get_embeddings(texts_to_embed)

            payload = {
                "fact": fact["fact"],
                "category": fact["category"],
            }
            if fact.get("tags"):
                payload["tags"] = fact["tags"]

            fact_points.append({
                "id": fact["id"],
                "vector": embeddings,
                "payload": payload,
            })

        with open(out_dir / "facts.json", "w") as f:
            json.dump(fact_points, f, indent=2)

        print(f"Generated fixture '{name}': "
              f"{len(todo_points)} todos, {len(fact_points)} facts "
              f"-> fixture_data/{name}/")


def _create_collections(client):
    """Drop and recreate empty eval collections."""
    for name in [TODOS_EVAL_COLLECTION, FACTS_EVAL_COLLECTION]:
        try:
            client.delete_collection(name)
        except Exception:
            pass

    # todos_eval (mirrors store/todos.py:39-68)
    client.create_collection(
        collection_name=TODOS_EVAL_COLLECTION,
        vectors_config=VectorParams(
            size=EMBEDDING_DIM,
            distance=Distance.COSINE,
            multivector_config=MultiVectorConfig(
                comparator=MultiVectorComparator.MAX_SIM
            ),
        ),
    )
    client.create_payload_index(
        collection_name=TODOS_EVAL_COLLECTION,
        field_name="title",
        field_schema=TextIndexParams(
            type=TextIndexType.TEXT,
            tokenizer=TokenizerType.WORD,
            lowercase=True,
        ),
    )
    client.create_payload_index(
        collection_name=TODOS_EVAL_COLLECTION,
        field_name="description",
        field_schema=TextIndexParams(
            type=TextIndexType.TEXT,
            tokenizer=TokenizerType.WORD,
            lowercase=True,
        ),
    )

    # facts_eval (mirrors store/facts.py:37-64)
    client.create_collection(
        collection_name=FACTS_EVAL_COLLECTION,
        vectors_config=VectorParams(
            size=EMBEDDING_DIM,
            distance=Distance.COSINE,
            multivector_config=MultiVectorConfig(
                comparator=MultiVectorComparator.MAX_SIM
            ),
        ),
    )
    client.create_payload_index(
        collection_name=FACTS_EVAL_COLLECTION,
        field_name="fact",
        field_schema=TextIndexParams(
            type=TextIndexType.TEXT,
            tokenizer=TokenizerType.WORD,
            lowercase=True,
        ),
    )
    client.create_payload_index(
        collection_name=FACTS_EVAL_COLLECTION,
        field_name="category",
        field_schema="keyword",
    )


def load_fixture_set(name: str | None = None):
    """Load a named fixture set into Qdrant eval collections.

    If name is None, creates empty collections.
    """
    client = get_client()
    _create_collections(client)

    if name is None:
        return

    todo_path = FIXTURE_DATA_DIR / name / "todos.json"
    fact_path = FIXTURE_DATA_DIR / name / "facts.json"

    if not todo_path.exists() or not fact_path.exists():
        raise FileNotFoundError(
            f"Fixture data for '{name}' not found. Run --generate-fixtures first."
        )

    with open(todo_path) as f:
        todo_points = json.load(f)
    if todo_points:
        client.upsert(
            collection_name=TODOS_EVAL_COLLECTION,
            points=[
                PointStruct(
                    id=fixture_id(p["id"]),
                    vector=p["vector"],
                    payload=p["payload"],
                )
                for p in todo_points
            ],
        )

    with open(fact_path) as f:
        fact_points = json.load(f)
    if fact_points:
        client.upsert(
            collection_name=FACTS_EVAL_COLLECTION,
            points=[
                PointStruct(
                    id=fixture_id(p["id"]),
                    vector=p["vector"],
                    payload=p["payload"],
                )
                for p in fact_points
            ],
        )


def cleanup_fixtures():
    """Delete test collections after eval run."""
    client = get_client()
    for name in [TODOS_EVAL_COLLECTION, FACTS_EVAL_COLLECTION]:
        try:
            client.delete_collection(name)
        except Exception:
            pass
