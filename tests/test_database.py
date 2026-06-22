from app.database import build_engine
from app.models import DocumentText, SearchIndex


def test_build_engine_creates_sqlite_parent_directory(tmp_path):
    database_path = tmp_path / "nested" / "app.db"
    engine = build_engine(f"sqlite:///{database_path}")

    try:
        assert database_path.parent.exists()
    finally:
        engine.dispose()


def test_v2_knowledge_tables_are_registered():
    assert DocumentText.__tablename__ == "document_texts"
    assert SearchIndex.__tablename__ == "search_index"
