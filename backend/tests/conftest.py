"""
Pytest configuration and shared fixtures for all tests.
"""
import pytest
import asyncio
import tempfile
import os
from uuid import uuid4
from unittest.mock import Mock, AsyncMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.main import app
from app.database import get_db, Base
from app.models import User, Document, Conversation, Message
from app.auth.jwt import JWTManager
from app.config import get_settings


# Test database setup
TEST_DATABASE_URL = "sqlite:///./test_comprehensive.db"
test_engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    """Override database dependency for testing."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


# Override the dependency
app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_db():
    """Create test database."""
    Base.metadata.create_all(bind=test_engine)
    yield test_engine
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def db_session(test_db):
    """Create a fresh database session for each test."""
    connection = test_db.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(test_db):
    """Create test client."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def test_user(db_session):
    """Create a test user."""
    user = User(
        username="testuser",
        email="test@example.com",
        password_hash="$2b$12$hashed_password"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_user(db_session):
    """Create an admin test user."""
    user = User(
        username="adminuser",
        email="admin@example.com",
        password_hash="$2b$12$hashed_password",
        role="admin"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user):
    """Create authentication headers for test user."""
    settings = get_settings()
    jwt_manager = JWTManager(settings.SECRET_KEY, settings.ALGORITHM, settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = jwt_manager.create_access_token(data={"sub": str(test_user.id), "username": test_user.username})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers(admin_user):
    """Create authentication headers for admin user."""
    settings = get_settings()
    jwt_manager = JWTManager(settings.SECRET_KEY, settings.ALGORITHM, settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = jwt_manager.create_access_token(data={"sub": str(admin_user.id), "username": admin_user.username})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_document(test_user, db_session):
    """Create a test document."""
    document = Document(
        user_id=test_user.id,
        filename="test_doc.pdf",
        original_name="Test Document.pdf",
        file_size=1024000,
        mime_type="application/pdf",
        file_path="/test/documents/test_doc.pdf",
        status="completed"
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    return document


@pytest.fixture
def test_conversation(test_user, db_session):
    """Create a test conversation."""
    conversation = Conversation(
        user_id=test_user.id,
        title="Test Conversation"
    )
    db_session.add(conversation)
    db_session.commit()
    db_session.refresh(conversation)
    return conversation


@pytest.fixture
def test_messages(test_conversation, db_session):
    """Create test messages for a conversation."""
    messages = []
    
    # User message
    user_message = Message(
        conversation_id=test_conversation.id,
        role="user",
        content="What is machine learning?"
    )
    db_session.add(user_message)
    messages.append(user_message)
    
    # Assistant message
    assistant_message = Message(
        conversation_id=test_conversation.id,
        role="assistant",
        content="Machine learning is a subset of artificial intelligence..."
    )
    db_session.add(assistant_message)
    messages.append(assistant_message)
    
    db_session.commit()
    for msg in messages:
        db_session.refresh(msg)
    
    return messages


@pytest.fixture
def sample_pdf_content():
    """Sample PDF content for testing."""
    return b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj

2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj

3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj

4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
72 720 Td
(Test PDF content for machine learning) Tj
ET
endstream
endobj

xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000074 00000 n 
0000000120 00000 n 
0000000179 00000 n 
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
274
%%EOF"""


@pytest.fixture
def sample_text_content():
    """Sample text content for testing."""
    return """Machine Learning Fundamentals

Machine learning is a method of data analysis that automates analytical model building. 
It is a branch of artificial intelligence based on the idea that systems can learn from data, 
identify patterns and make decisions with minimal human intervention.

Key concepts include:
- Supervised learning
- Unsupervised learning  
- Reinforcement learning
- Neural networks
- Deep learning

Applications are found in many industries including healthcare, finance, and technology."""


@pytest.fixture
def temp_file():
    """Create a temporary file for testing."""
    with tempfile.NamedTemporaryFile(delete=False) as f:
        yield f.name
    os.unlink(f.name)


@pytest.fixture
def mock_ai_service():
    """Mock AI service for testing."""
    mock_service = Mock()
    mock_service.generate_text = AsyncMock(return_value="Generated AI response")
    mock_service.create_embeddings = AsyncMock(return_value=[0.1, 0.2, 0.3])
    mock_service.is_available = AsyncMock(return_value=True)
    return mock_service


@pytest.fixture
def mock_vector_store():
    """Mock vector store for testing."""
    mock_store = Mock()
    mock_store.add_vectors = AsyncMock(return_value=["vector_1", "vector_2"])
    mock_store.search = AsyncMock(return_value=[
        {"id": "vector_1", "score": 0.9, "metadata": {"content": "test content"}}
    ])
    mock_store.delete_vectors = AsyncMock(return_value=True)
    return mock_store


@pytest.fixture
def mock_storage():
    """Mock storage service for testing."""
    mock_storage = Mock()
    mock_storage.upload_file = AsyncMock(return_value="/test/path/file.pdf")
    mock_storage.download_file = AsyncMock(return_value=b"file content")
    mock_storage.delete_file = AsyncMock(return_value=True)
    mock_storage.list_files = AsyncMock(return_value=["file1.pdf", "file2.txt"])
    return mock_storage


# Pytest configuration
def pytest_configure(config):
    """Configure pytest."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "performance: mark test as performance test"
    )
    config.addinivalue_line(
        "markers", "e2e: mark test as end-to-end test"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers."""
    for item in items:
        # Add integration marker to integration tests
        if "integration" in item.nodeid:
            item.add_marker(pytest.mark.integration)
        
        # Add performance marker to performance tests
        if "performance" in item.nodeid:
            item.add_marker(pytest.mark.performance)
        
        # Add e2e marker to end-to-end tests
        if "e2e" in item.nodeid or "end_to_end" in item.nodeid:
            item.add_marker(pytest.mark.e2e)


# Async test support
@pytest.fixture(scope="session")
def anyio_backend():
    """Use asyncio backend for async tests."""
    return "asyncio"