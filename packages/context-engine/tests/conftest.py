import pytest
from qdrant_client import QdrantClient
from src.context_retriever import ContextRetriever
from src.ast_analyzer import TreeSitterAnalyzer


@pytest.fixture
def memory_qdrant_client():
    return QdrantClient(":memory:")


@pytest.fixture
def context_retriever(memory_qdrant_client):
    return ContextRetriever(qdrant_client=memory_qdrant_client)


@pytest.fixture
def ast_analyzer():
    return TreeSitterAnalyzer()
