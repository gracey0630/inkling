from contracts import Evidence
from rag.stub import retrieve


def test_stub_matches_contract():
    results = retrieve("what is the luteal phase?")
    assert results and all(isinstance(e, Evidence) for e in results)
