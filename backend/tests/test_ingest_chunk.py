from app.services.ingest import chunk_text


def test_chunk_text_basic():
    text = "word " * 500
    chunks = chunk_text(text, chunk_size=100, overlap=20)
    assert len(chunks) > 1
    assert all(len(c) <= 120 for c in chunks)


def test_chunk_empty():
    assert chunk_text("") == []
    assert chunk_text("   ") == []
