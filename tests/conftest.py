"""Pytest configuration and fixtures."""
import os
import pytest
from unittest.mock import patch, MagicMock

from tests.fixtures.chroma_mock import create_mock_v2_chroma_client, create_mock_chroma_client, create_mock_collection
from tests.fixtures.redis_mock import create_mock_redis_client


@pytest.fixture
def mock_chroma_client():
    """Mock ChromaDB client fixture."""
    return create_mock_v2_chroma_client()


@pytest.fixture
def mock_redis_client():
    """Mock Redis client fixture."""
    return create_mock_redis_client()


@pytest.fixture
def mock_collection():
    """Mock ChromaDB collection fixture."""
    return create_mock_collection()


@pytest.fixture
def mock_openai_key():
    """Mock OpenAI API key fixture."""
    return "sk-test-key-12345"


@pytest.fixture
def sample_memory_data():
    """Sample memory data for testing."""
    return {
        "user_id": "test_user",
        "content": "User loves sci-fi books.",
        "layer": "semantic",
        "type": "explicit",
        "embedding": [0.1] * 16,
        "confidence": 0.9,
        "ttl": None,
        "metadata": {"tags": ["behavior", "personal"]}
    }


@pytest.fixture
def sample_transcript():
    """Sample transcript data for testing."""
    return {
        "user_id": "test_user",
        "history": [
            {"role": "user", "content": "I love sci-fi books."},
            {"role": "assistant", "content": "That's great! What's your favorite author?"}
        ],
        "metadata": {"conversation_id": "test_conv_123"}
    }


@pytest.fixture
def mock_llm_response():
    """Mock LLM response for extraction."""
    return {
        "worthy": True,
        "confidence": 0.8,
        "tags": ["behavior"],
        "reasons": ["Contains user preference"]
    }


@pytest.fixture
def mock_extraction_items():
    """Mock extraction items from LLM."""
    return [
        {
            "content": "User loves sci-fi books.",
            "type": "explicit",
            "layer": "semantic",
            "ttl": None,
            "confidence": 0.9,
            "tags": ["behavior", "personal"],
            "project": None,
            "relationship": None,
            "learning_journal": None
        }
    ]


@pytest.fixture(autouse=True)
def mock_external_dependencies(mock_chroma_client, mock_redis_client, mock_openai_key):
    """Automatically mock external dependencies for all tests."""
    with patch('src.dependencies.chroma.get_chroma_client', return_value=mock_chroma_client), \
         patch('src.dependencies.redis_client.get_redis_client', return_value=mock_redis_client), \
         patch.dict(os.environ, {'OPENAI_API_KEY': mock_openai_key}):
        yield


@pytest.fixture
def app_with_mocks(mock_chroma_client, mock_redis_client, mock_openai_key):
    """FastAPI app with mocked dependencies."""
    from src.app import app
    
    # Ensure collections exist
    collection = mock_chroma_client.get_or_create_collection("memories_3072")
    
    with patch('src.dependencies.chroma.get_chroma_client', return_value=mock_chroma_client), \
         patch('src.dependencies.redis_client.get_redis_client', return_value=mock_redis_client), \
         patch.dict(os.environ, {'OPENAI_API_KEY': mock_openai_key}):
        yield app
