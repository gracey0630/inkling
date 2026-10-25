"""RAG layer stub: contract-shaped fake evidence until the real retriever lands."""

from contracts import Evidence, load_fixture


def retrieve(query: str, user_context: dict | None = None) -> list[Evidence]:
    return [Evidence.model_validate(e) for e in load_fixture("evidence")]
