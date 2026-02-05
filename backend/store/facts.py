from dataclasses import dataclass

from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchText,
    MultiVectorComparator,
    MultiVectorConfig,
    PointStruct,
    TextIndexParams,
    TextIndexType,
    TokenizerType,
    VectorParams,
)

from ai.logging_config import get_logger
from models import FactItem

from .embeddings import get_embedding, get_embeddings
from .qdrant import EMBEDDING_DIM, get_client

log = get_logger("store.facts")

COLLECTION_NAME = "facts"


def ensure_collection() -> None:
    """Ensure the facts collection exists with proper schema."""
    client = get_client()

    collections = client.get_collections().collections
    exists = any(c.name == COLLECTION_NAME for c in collections)

    if not exists:
        log.info(f"Creating collection: {COLLECTION_NAME}")
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=EMBEDDING_DIM,
                distance=Distance.COSINE,
                multivector_config=MultiVectorConfig(
                    comparator=MultiVectorComparator.MAX_SIM
                ),
            ),
        )

        log.info("Creating text index for fact field")
        client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name="fact",
            field_schema=TextIndexParams(
                type=TextIndexType.TEXT,
                tokenizer=TokenizerType.WORD,
                lowercase=True,
            ),
        )

        log.info("Creating keyword index for category field")
        client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name="category",
            field_schema="keyword",
        )
        log.info(f"Collection {COLLECTION_NAME} created successfully")
    else:
        log.debug(f"Collection {COLLECTION_NAME} already exists")


def save_fact(fact: FactItem, tags: list[str] | None = None) -> FactItem:
    """Save fact with variable-length multivector based on tags."""
    client = get_client()

    log.info(f"Saving fact: {fact.id} - {fact.fact[:50]}...")

    texts_to_embed = tags or fact.tags or [fact.fact]

    log.debug(f"Embedding {len(texts_to_embed)} texts for fact {fact.id}")
    embeddings = get_embeddings(texts_to_embed)

    payload: dict[str, str | list[str] | None] = {
        "fact": fact.fact,
        "category": fact.category,
    }

    if fact.tags:
        payload["tags"] = fact.tags
    if fact.created_at:
        payload["created_at"] = fact.created_at

    point = PointStruct(
        id=fact.id,
        vector=embeddings,
        payload=payload,
    )

    client.upsert(collection_name=COLLECTION_NAME, points=[point])
    log.debug(f"Fact {fact.id} saved to Qdrant")

    return fact


@dataclass
class FactSearchResult:
    """A search result containing a fact and its relevance score."""

    fact: FactItem
    score: float


def search_facts(query: str, limit: int = 10) -> list[FactSearchResult]:
    """Hybrid search: vector similarity + keyword matching."""
    client = get_client()

    log.info(f"Searching facts for: {query}")

    results_by_id: dict[str, FactSearchResult] = {}

    # 1. Vector search
    query_embedding = get_embedding(query)
    vector_results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_embedding,
        limit=limit,
    )

    for point in vector_results.points:
        payload = point.payload or {}
        fact = FactItem(
            id=str(point.id),
            fact=payload.get("fact", ""),
            category=payload.get("category", "other"),
            tags=payload.get("tags", []),
            created_at=payload.get("created_at"),
        )
        results_by_id[fact.id] = FactSearchResult(fact=fact, score=point.score or 0.0)

    log.info(f"Vector search found {len(vector_results.points)} facts")

    # 2. Keyword search
    keyword_results, _ = client.scroll(
        collection_name=COLLECTION_NAME,
        scroll_filter=Filter(
            should=[
                FieldCondition(key="fact", match=MatchText(text=query)),
            ]
        ),
        limit=limit,
    )

    for point in keyword_results:
        fact_id = str(point.id)
        if fact_id not in results_by_id:
            payload = point.payload or {}
            fact = FactItem(
                id=fact_id,
                fact=payload.get("fact", ""),
                category=payload.get("category", "other"),
                tags=payload.get("tags", []),
                created_at=payload.get("created_at"),
            )
            results_by_id[fact_id] = FactSearchResult(fact=fact, score=0.5)

    log.info(f"Keyword search found {len(keyword_results)} facts")

    search_results = sorted(
        results_by_id.values(), key=lambda r: r.score, reverse=True
    )[:limit]

    log.info(f"Returning {len(search_results)} combined results")
    return search_results


def list_facts() -> list[FactItem]:
    """List all facts."""
    client = get_client()

    results, _ = client.scroll(collection_name=COLLECTION_NAME, limit=1000)

    facts = []
    for point in results:
        payload = point.payload or {}
        fact = FactItem(
            id=str(point.id),
            fact=payload.get("fact", ""),
            category=payload.get("category", "other"),
            tags=payload.get("tags", []),
            created_at=payload.get("created_at"),
        )
        facts.append(fact)

    log.info(f"Listed {len(facts)} facts")
    return facts
