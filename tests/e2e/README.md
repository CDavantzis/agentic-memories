# E2E Tests - Simplified

This directory contains end-to-end tests that run against the deployed application using the standard Docker deployment.

## Quick Start

### 1. Start the Application
```bash
# Start the application using standard Docker deployment
docker-compose up -d

# Or start manually
uvicorn src.app:app --reload --host 0.0.0.0 --port 8080
```

### 2. Run E2E Tests
```bash
# Run all E2E tests
./tests/e2e/run_e2e_tests.sh

# Or run specific test types
./tests/e2e/run_e2e_tests.sh api
./tests/e2e/run_e2e_tests.sh evaluation
./tests/e2e/run_e2e_tests.sh pytest
```

## How It Works

The E2E test suite:
1. **Checks if containers are running** - Uses existing Docker deployment
2. **Starts containers if needed** - Falls back to `docker-compose up -d`
3. **Waits for app to be ready** - Health check on `http://localhost:8080`
4. **Runs comprehensive tests** - API, evaluation, and performance tests
5. **Collects results** - Logs and metrics in `tests/e2e/logs/` and `tests/e2e/results/`

## Test Categories

### **API Tests**
- Health endpoints (basic and full)
- Store and retrieve functionality
- Structured retrieval
- Error handling
- Memory normalization

### **Evaluation Tests**
- Memory quality against ground truth
- Normalization quality (User prefix, pronoun handling)
- Categorization quality (types, layers, tags)
- Retrieval relevance

### **Comprehensive Tests**
- Generated test data (20 conversations)
- Quality metrics (recall, precision, F1)
- Performance testing
- Error handling robustness

## Test Data

The suite uses generated test data with:
- **Consistent user ID**: `test_user_22`
- **20 conversations** across 4 topics (sci-fi, travel, work, health)
- **3 complexity levels** (simple, medium, complex)
- **73 expected memories** for quality evaluation

## Results

Test results are saved to:
- **`tests/e2e/logs/`** - Application logs and system info
- **`tests/e2e/results/`** - Test results, health checks, and reports

## Commands

```bash
# Run all tests
./tests/e2e/run_e2e_tests.sh all

# Run specific test types
./tests/e2e/run_e2e_tests.sh setup      # Setup environment only
./tests/e2e/run_e2e_tests.sh connectivity  # Connectivity tests
./tests/e2e/run_e2e_tests.sh api        # API tests
./tests/e2e/run_e2e_tests.sh evaluation # Evaluation tests
./tests/e2e/run_e2e_tests.sh pytest    # Pytest tests
./tests/e2e/run_e2e_tests.sh performance # Performance tests
./tests/e2e/run_e2e_tests.sh metrics   # Collect logs and metrics
```

## Requirements

- Docker and Docker Compose
- Python 3.8+
- `jq` for JSON processing
- `pytest` and `requests` for testing

## Troubleshooting

### Application not starting
```bash
# Check if containers are running
docker ps

# Check logs
docker-compose logs

# Restart if needed
docker-compose restart
```

### Tests failing
```bash
# Check if app is responding
curl http://localhost:8080/health

# Run with verbose output
pytest tests/e2e/ -v --tb=long
```

### Clean up
```bash
# Stop containers
docker-compose down

# Clean up test data
rm -rf tests/e2e/logs/ tests/e2e/results/
```

## Integration

The E2E tests are designed to work with:
- **Standard Docker deployment** (`docker-compose up -d`)
- **Manual deployment** (uvicorn command)
- **CI/CD pipelines** (GitHub Actions, etc.)

The tests automatically detect if containers are running and use the existing deployment, making them perfect for integration into development workflows and CI/CD pipelines.
