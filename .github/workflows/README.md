# GitHub Actions Workflows

This directory contains CI/CD workflows for the `aiecs` project.

## 📋 Workflows Overview

| Workflow | File | Trigger | Purpose | Duration |
|----------|------|---------|---------|----------|
| **Unit Tests** | `ci-unit.yml` | Push, PR | Run unit tests on Python 3.11 & 3.12 | ~5 min |
| **Integration Tests** | `ci-integration.yml` | Push/PR to main | Test with Redis & PostgreSQL | ~10 min |
| **Code Quality** | `ci-quality.yml` | Push, PR | Lint, format, type check, security | ~5 min |
| **E2E Tests** | `ci-e2e.yml` | Manual, Release, Weekly | Real API tests (LLMs, tools) | ~15 min |
| **Publish (PyPI)** | `publish-to-pypi.yml` | Release published | Deploy to production PyPI | ~3 min |
| **Publish (Test)** | `publish-to-testpypi.yml` | Manual | Deploy to Test PyPI | ~3 min |

---

## 🚀 CI/CD Workflows

### 1. Unit Tests (`ci-unit.yml`)

**Purpose**: Fast, isolated unit tests for core functionality.

**Triggers**:
- Push to any branch
- Pull requests
- Manual dispatch

**Features**:
- Multi-Python version matrix (3.11, 3.12)
- Poetry dependency caching
- Code coverage reporting (Codecov + HTML)
- PR coverage comments
- Runs tests with `-m unit` marker

**Configuration**:
- Timeout: 10 minutes
- Coverage threshold: None (informational)
- Artifacts: Coverage reports (7 days)

**Example Run**:
```bash
poetry run pytest test/unit/ -m unit --cov=aiecs --cov-report=xml
```

---

### 2. Integration Tests (`ci-integration.yml`)

**Purpose**: Test component interactions with real services.

**Triggers**:
- Push to `main` branch
- Pull requests to `main`
- Manual dispatch

**Features**:
- Redis service container (port 6379)
- PostgreSQL service container (port 5432)
- Service health checks
- Environment variable setup
- Coverage reporting

**Services**:
```yaml
Redis: redis:7-alpine
PostgreSQL: postgres:15-alpine
```

**Configuration**:
- Timeout: 20 minutes
- Test marker: `-m integration`
- Artifacts: Test results + coverage (14 days)

**Environment Variables**:
```bash
REDIS_HOST=localhost
REDIS_PORT=6379
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=test_user
POSTGRES_PASSWORD=test_password
POSTGRES_DB=test_db
```

---

### 3. Code Quality (`ci-quality.yml`)

**Purpose**: Ensure code quality, style, and security.

**Triggers**:
- Push to any branch
- Pull requests
- Manual dispatch

**Checks**:
1. **Black**: Code formatting (`--check`)
2. **Flake8**: Linting (max-line-length=120)
3. **MyPy**: Type checking (continue-on-error)
4. **Bandit**: Security scanning (JSON report)
5. **Safety**: Dependency vulnerability check
6. **isort**: Import sorting

**Configuration**:
- Timeout: 10 minutes
- Fail on: Black, Flake8 (others are warnings)
- Artifacts: Security reports (30 days)

**Example Commands**:
```bash
poetry run black --check --diff aiecs/ test/
poetry run flake8 aiecs/ test/ --max-line-length=120
poetry run mypy aiecs/ --ignore-missing-imports
poetry run bandit -r aiecs/ -f json
```

---

### 4. E2E Tests (`ci-e2e.yml`)

**Purpose**: End-to-end tests with real API calls.

**Triggers**:
- Release published
- Manual dispatch (with provider selection)
- Weekly schedule (Sunday 00:00 UTC)

**Features**:
- Real API key usage (GitHub Secrets)
- Provider selection (all, openai, google, vertex, xai)
- Cost tracking and reporting
- Test result artifacts
- Failure notifications

**Manual Trigger Options**:
- `provider`: Choose LLM provider to test
  - `all` (default): Test all providers
  - `openai`: OpenAI/GPT only
  - `google`: Google AI/Gemini only
  - `vertex`: Vertex AI only
  - `xai`: xAI/Grok only

**Configuration**:
- Timeout: 30 minutes
- Test marker: `-m e2e`
- Artifacts: Test results + HTML report (30 days)

**Cost Estimates**:
- OpenAI test: ~$0.00003
- Google/Vertex test: ~$0.000005
- xAI test: ~$0.00003
- Search test: ~$0.01
- **Total suite**: < $0.05 per run

---

## 🔑 GitHub Secrets Configuration

### Required Secrets for E2E Tests

To run E2E tests, configure the following secrets in your GitHub repository:

**Settings → Secrets and variables → Actions → New repository secret**

#### LLM Provider Secrets

| Secret Name | Description | Required For | How to Get |
|-------------|-------------|--------------|------------|
| `OPENAI_API_KEY` | OpenAI API key | OpenAI/GPT tests | https://platform.openai.com/api-keys |
| `GOOGLEAI_API_KEY` | Google AI API key | Google AI/Gemini tests | https://makersuite.google.com/app/apikey |
| `VERTEX_PROJECT_ID` | GCP Project ID | Vertex AI tests | GCP Console → Project Info |
| `VERTEX_LOCATION` | Vertex AI region | Vertex AI tests | e.g., `us-central1` |
| `XAI_API_KEY` | xAI API key | xAI/Grok tests | https://console.x.ai/ |

#### Tool/Service Secrets

| Secret Name | Description | Required For | How to Get |
|-------------|-------------|--------------|------------|
| `GOOGLE_CSE_ID` | Custom Search Engine ID | Search tool tests | https://programmablesearchengine.google.com/ |
| `GOOGLE_CSE_API_KEY` | Google CSE API key | Search tool tests | GCP Console → APIs & Services → Credentials |
| `FRED_API_KEY` | FRED economic data API | APISource tests (optional) | https://fred.stlouisfed.org/docs/api/api_key.html |
| `NEWSAPI_API_KEY` | News API key | APISource tests (optional) | https://newsapi.org/register |

### How to Configure Secrets

#### Step 1: Navigate to Repository Settings
1. Go to your GitHub repository
2. Click **Settings** (top right)
3. Click **Secrets and variables** → **Actions** (left sidebar)

#### Step 2: Add New Secret
1. Click **New repository secret**
2. Enter the secret name (exact match from table above)
3. Paste the secret value (API key, project ID, etc.)
4. Click **Add secret**

#### Step 3: Verify Configuration
After adding secrets, you can verify them by:
1. Running the E2E workflow manually: **Actions** → **E2E Tests** → **Run workflow**
2. Check the "Check API keys availability" step in the workflow logs
3. Keys are masked in logs (shown as `***`)

### Security Best Practices

1. **Never commit secrets**: Use GitHub Secrets, not `.env` files
2. **Rotate keys regularly**: Update secrets every 90 days
3. **Use service accounts**: For GCP/Vertex, use dedicated service accounts
4. **Monitor usage**: Set up billing alerts for API usage
5. **Restrict access**: Only give workflow access to necessary secrets
6. **Test locally first**: Use `.env` file locally before adding to GitHub

### Cost Management

E2E tests use minimal API calls to reduce costs:
- **Minimal prompts**: "Say 'OK'" (5-10 tokens)
- **Skip if no key**: Tests auto-skip when secrets not configured
- **Manual trigger**: E2E tests don't run on every push
- **Provider selection**: Test only specific providers when needed

**Monthly cost estimate** (weekly runs): ~$0.20/month

---

## 📊 Test Pyramid Structure

Our tests follow the testing pyramid:

```
       /\
      /E2E\       10% - Real APIs, complete workflows
     /----\
    / Int \       20% - Service interactions, databases
   /-------\
  /  Unit  \      70% - Fast, isolated, mocked
 /---------\
```

### Test Distribution

| Type | Count | Marker | Duration | Frequency |
|------|-------|--------|----------|-----------|
| Unit | ~3,500 | `unit` | < 1 min | Every push |
| Integration | ~150 | `integration` | < 5 min | Push to main |
| E2E | ~24 | `e2e` | < 15 min | Weekly/Release |
| Performance | ~10 | `performance` | < 2 min | Manual |

---

## 🎯 Test Markers

Use pytest markers to run specific test types:

```bash
# Run unit tests only
pytest -m unit

# Run integration tests
pytest -m integration

# Run E2E tests
pytest -m e2e

# Run specific provider E2E tests
pytest -m "e2e and openai"
pytest -m "e2e and google"
pytest -m "e2e and vertex"
pytest -m "e2e and xai"

# Exclude slow tests
pytest -m "not slow"

# Exclude expensive tests
pytest -m "not expensive"

# Run tests requiring specific services
pytest -m requires_redis
pytest -m requires_postgres
```

---

## 🚀 Local Testing

### Prerequisites

```bash
# Install dependencies
poetry install

# Install dev dependencies
poetry install --with dev
```

### Run Tests Locally

```bash
# Run unit tests (fast, no services needed)
poetry run pytest test/unit/ -m unit

# Run integration tests (needs Redis & PostgreSQL)
docker-compose up -d redis postgres
poetry run pytest test/integration/ -m integration

# Run E2E tests (needs API keys in .env)
cp .env.example .env
# Edit .env with your API keys
poetry run pytest test/e2e/ -m e2e

# Run specific E2E provider
poetry run pytest test/e2e/ -m "e2e and openai"

# Run with coverage
poetry run pytest test/unit/ -m unit --cov=aiecs --cov-report=html
```

### Clean Cache Before Testing

```bash
# Clean pytest cache
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true
rm -rf .pytest_cache

# Clean coverage data
rm -rf .coverage htmlcov/
```

---

## 📈 Coverage Reports

### Codecov Integration

Coverage reports are automatically uploaded to Codecov for:
- Unit tests (Python 3.11 only)
- Integration tests

**Badge**: Add to README.md
```markdown
[![codecov](https://codecov.io/gh/YOUR_ORG/YOUR_REPO/branch/main/graph/badge.svg)](https://codecov.io/gh/YOUR_ORG/YOUR_REPO)
```

### Local Coverage

```bash
# Generate HTML coverage report
poetry run pytest test/unit/ -m unit --cov=aiecs --cov-report=html

# Open in browser
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

---

## 🔧 Troubleshooting

### Common Issues

#### 1. Tests Failing Due to Missing Dependencies
```bash
# Install all dependencies
poetry install --with dev

# Check installed packages
poetry show
```

#### 2. Service Connection Errors (Integration Tests)
```bash
# Check service status
docker ps

# Restart services
docker-compose restart redis postgres

# Check logs
docker-compose logs redis postgres
```

#### 3. E2E Tests Skipped
- **Cause**: API keys not configured
- **Solution**: Add secrets to GitHub or `.env` file locally

#### 4. Timeout Errors
- **Unit tests**: Should complete in < 5 minutes (timeout: 10 min)
- **Integration tests**: Should complete in < 10 minutes (timeout: 20 min)
- **E2E tests**: Should complete in < 15 minutes (timeout: 30 min)

If tests timeout:
- Check for infinite loops
- Verify service connectivity
- Increase timeout in `pyproject.toml` or workflow

#### 5. Coverage Upload Fails
- **Cause**: Codecov token not configured or rate limit
- **Solution**: Set `CODECOV_TOKEN` secret (optional but recommended)

---

## 📚 Additional Resources

- **Pytest Documentation**: https://docs.pytest.org/
- **GitHub Actions Documentation**: https://docs.github.com/en/actions
- **Poetry Documentation**: https://python-poetry.org/docs/
- **Codecov Documentation**: https://docs.codecov.com/

---

## 🤝 Contributing

When adding new tests:

1. **Use appropriate markers**: Add `@pytest.mark.unit`, `@pytest.mark.integration`, or `@pytest.mark.e2e`
2. **Follow directory structure**: Place tests in correct directories (`test/unit/`, `test/integration/`, `test/e2e/`)
3. **Keep tests fast**: Unit tests < 1s, Integration < 5s, E2E < 30s
4. **Mock external calls**: Use mocks for unit/integration tests
5. **Document expensive tests**: Add `@pytest.mark.expensive` for costly E2E tests
6. **Update this README**: When adding new workflows or secrets

---

**Last Updated**: December 21, 2025  
**Maintained By**: AIECS Team
