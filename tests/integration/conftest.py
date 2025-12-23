"""Integration test configuration with real HTTP client for e2e-style tests.

Provides fixtures for tests that need to hit the running Docker container
with real database connections, as opposed to mocked database tests.
"""
import os
import time
import pytest
import requests
from dataclasses import dataclass
from uuid import uuid4


@dataclass
class E2ETestConfig:
    """Configuration for e2e-style integration tests."""
    api_base_url: str = "http://localhost:8080"
    timeout: int = 30


@pytest.fixture(scope="session")
def e2e_config():
    """E2E test configuration fixture."""
    return E2ETestConfig()


@pytest.fixture(scope="session")
def app_ready(e2e_config):
    """Wait for deployed application to be ready."""
    max_retries = 30
    for i in range(max_retries):
        try:
            response = requests.get(f"{e2e_config.api_base_url}/health", timeout=5)
            if response.status_code == 200:
                break
        except requests.exceptions.RequestException:
            pass
        time.sleep(1)
    else:
        pytest.skip("Application not available at localhost:8080")

    yield e2e_config


@pytest.fixture
def real_api_client(app_ready):
    """Real HTTP API client for e2e-style testing against running Docker container.

    Use this fixture for tests that need real database connections.
    The fixture name 'real_api_client' distinguishes it from the mocked 'api_client'.
    """
    session = requests.Session()
    yield session
    session.close()


@pytest.fixture
def unique_user_id():
    """Generate unique user ID for test isolation."""
    return f"e2e-test-{uuid4().hex[:8]}"
