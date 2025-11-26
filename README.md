# UAT Automation Service - LLM-Powered Test Generation

## Overview

An advanced, production-ready UAT automation platform that leverages Large Language Models (LLMs) to intelligently parse user stories, generate comprehensive test scenarios, and validate web applications against business requirements. The system uses Groq's free API with Llama models to transform natural language requirements into executable tests with intelligent DOM mapping and adaptive test generation.

**Target Users:** B2B SaaS vendors, IT service companies, and regulated industries (BFSI, healthcare, ERP) who need automated, traceable UAT validation that bridges the gap between business requirements and technical implementation.

## Architecture

### V2 Architecture (Current - LLM-Powered)

The V2 architecture is a complete rewrite featuring:

- **LLM Integration**: Groq API with Llama 3.1 models for intelligent story parsing and scenario generation
- **Multi-Strategy Element Finding**: Semantic DOM analysis with fuzzy matching and context-aware disambiguation
- **Parallel Test Execution**: Configurable concurrency with smart retry logic and flaky test detection
- **Advanced Reporting**: Business-friendly HTML/JSON/PDF reports with traceability and analytics
- **Service-Oriented Design**: Modular architecture with clear separation of concerns

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client Layer                              │
│  ┌──────────────────┐         ┌──────────────────┐             │
│  │   Web UI         │         │  External APIs   │             │
│  │   Dashboard      │         │  (Jira, Azure)   │             │
│  └──────────────────┘         └──────────────────┘             │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                      API Gateway Layer                           │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  FastAPI Server (v1 POC + v2 API)                        │  │
│  │  - OpenAPI/Swagger Docs                                  │  │
│  │  - API Key Authentication                                │  │
│  │  - CORS & Rate Limiting                                  │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                       Service Layer                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ LLM Service  │  │ Story Parser │  │ Test Runner  │         │
│  │ (Groq API)   │  │   Service    │  │   Service    │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│  ┌──────────────┐  ┌──────────────┐                            │
│  │  Reporting   │  │   Storage    │                            │
│  │   Service    │  │   Service    │                            │
│  └──────────────┘  └──────────────┘                            │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                     Execution Layer                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │  Playwright  │  │  DOM Mapper  │  │   Element    │         │
│  │    Engine    │  │              │  │   Finder     │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                       Data Layer                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   SQLite/    │  │    Redis     │  │     File     │         │
│  │  PostgreSQL  │  │    Cache     │  │   Storage    │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└─────────────────────────────────────────────────────────────────┘
```

### Key Features

#### 1. LLM-Powered Story Parsing
- **Primary Model**: llama-3.1-70b-versatile for complex story analysis
- **Fallback Model**: llama-3.1-8b-instant for rate-limited scenarios
- **Legacy NLP Fallback**: Graceful degradation to rule-based parsing
- **Structured Prompts**: JSON schema validation for consistent outputs
- **Smart Retry**: Exponential backoff with 3 retry attempts

#### 2. Intelligent Test Generation
- **Comprehensive Scenarios**: Positive, negative, and edge case generation
- **Dependency Detection**: Identifies interdependencies between acceptance criteria
- **Priority Assignment**: Critical/high/medium/low based on business impact
- **Given-When-Then Format**: BDD-style scenarios for clarity

#### 3. Advanced Element Discovery
- **Multi-Strategy Approach**: data-testid → aria-label → label-for → placeholder → text → role
- **Fuzzy Matching**: 80% similarity threshold using semantic analysis
- **Context-Aware Disambiguation**: Uses parent containers and sibling elements
- **LLM Selector Suggestions**: Suggests alternatives when elements not found

#### 4. Parallel Test Execution
- **Configurable Concurrency**: Default 3 parallel scenarios (1-10 range)
- **Smart Retry Logic**: Retry once after 2s delay
- **Flaky Test Detection**: Tracks tests that pass on retry
- **Comprehensive Diagnostics**: Screenshots, console logs, network capture

#### 5. Enterprise Reporting
- **Multiple Formats**: HTML, JSON, PDF export
- **Traceability Matrix**: Story → criteria → scenario → result mapping
- **Executive Summary**: Pass/fail percentages and trend analysis
- **Visual Insights**: Charts, timelines, and suggested fixes

## Quick Start

### Prerequisites

- **Python 3.11+** (for UAT service)
- **Node.js 18+** (for sample application)
- **Docker & Docker Compose** (recommended for production)
- **Groq API Key** (free at https://console.groq.com/keys)

### Option 1: Docker Compose (Recommended)

```bash
# 1. Clone the repository
git clone <repository-url>
cd <repository-name>

# 2. Set up environment variables
cp uat-service/.env.example uat-service/.env
# Edit .env and set your GROQ_API_KEY

# 3. Start all services
docker-compose up -d

# 4. Access the services
# - UAT Service: http://localhost:8000
# - API Docs: http://localhost:8000/docs
# - Sample App: http://localhost:5173

# 5. View logs
docker-compose logs -f uat-service

# 6. Stop services
docker-compose down
```

### Option 2: Local Development

#### Start Sample Application

```bash
cd sample-app
npm install
npm run dev        # Frontend on http://localhost:5173
npm run server     # Backend on http://localhost:3000
```

#### Start UAT Service

```bash
cd uat-service

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Set up environment
cp .env.example .env
# Edit .env and set your GROQ_API_KEY

# Run the service
uvicorn app.main:app --reload --port 8000
```

## Usage

### Web UI (V1 POC Interface)

1. Open http://localhost:8000
2. Enter user story details:
   - **Title**: "Login as a user"
   - **Acceptance Criteria**: (separate scenarios with blank lines)
     ```
     Given I am on the login page
     When I enter valid credentials
     Then I should see the dashboard
     
     When I enter invalid credentials
     Then I should see an error message
     ```
   - **Target URL**: http://localhost:5173
3. Click "Run UAT" to execute tests
4. View results in the generated HTML report

### REST API (V2)

#### Submit a Story

```bash
POST http://localhost:8000/api/v2/stories
Content-Type: application/json

{
  "title": "User Login",
  "description": "As a user, I want to log in to access my account",
  "acceptance_criteria": [
    {
      "text": "Given I am on the login page, When I enter valid credentials, Then I should be redirected to the dashboard"
    },
    {
      "text": "When I enter invalid credentials, Then I should see an error message"
    }
  ],
  "metadata": {
    "module": "authentication",
    "priority": "critical"
  }
}
```

#### Execute Tests

```bash
POST http://localhost:8000/api/v2/stories/{story_id}/run
Content-Type: application/json

{
  "target_url": "http://localhost:5173",
  "execution_config": {
    "concurrency": 3,
    "headless": true,
    "screenshot_on_failure": true
  }
}
```

#### Retrieve Results

```bash
GET http://localhost:8000/api/v2/runs/{run_id}
```

#### Query Runs

```bash
GET http://localhost:8000/api/v2/runs?story_id={id}&status=passed&from=2024-01-01
```

### API Documentation

Interactive API documentation is available at:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Configuration

### Environment Variables

Key configuration options (see `.env.example` for complete list):

```bash
# LLM Configuration (Required)
GROQ_API_KEY=your_api_key_here
MODEL_PRIMARY=llama-3.1-70b-versatile
MODEL_FALLBACK=llama-3.1-8b-instant

# Test Execution
CONCURRENCY=3
TEST_TIMEOUT=30000
HEADLESS_MODE=true

# Sample Application
SAMPLE_APP_URL=http://localhost:5173

# Database
DATABASE_URL=sqlite:///./uat_service.db

# Cache
REDIS_URL=redis://localhost:6379
ENABLE_CACHE=true

# API
API_PORT=8000
ENABLE_API_DOCS=true
ENABLE_CORS=true

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
```

### CLI Arguments

The UAT service supports command-line arguments for configuration overrides:

```bash
# Start service with default configuration
python -m app

# Override concurrency and headless mode
python -m app --concurrency 5 --headless false

# Run in legacy mode (V1 NLP)
python -m app --legacy

# Override multiple settings
python -m app --port 9000 --log-level DEBUG --concurrency 3

# Production mode
python -m app --environment production --headless true --debug false

# Enable hot reload for development
python -m app --reload

# Override LLM models
python -m app --model-primary llama-3.1-8b-instant --model-fallback llama-3.1-8b-instant

# Override sample app URL
python -m app --sample-app-url http://localhost:3000

# View all available options
python -m app --help
```

#### Available CLI Options

**Server Configuration:**
- `--host`: API host (default: 0.0.0.0)
- `--port`: API port (default: 8000)
- `--reload`: Enable hot reload for development

**LLM Configuration:**
- `--groq-api-key`: Groq API key
- `--model-primary`: Primary LLM model
- `--model-fallback`: Fallback LLM model

**Test Execution:**
- `--concurrency`: Number of parallel scenarios (1-10)
- `--test-timeout`: Test step timeout in milliseconds
- `--headless`: Run browser in headless mode (true/false)
- `--slow-mo`: Browser slow motion delay for debugging
- `--retry-attempts`: Number of retry attempts (0-5)

**Application:**
- `--sample-app-url`: Sample application URL

**Database:**
- `--database-url`: Database connection URL

**Cache:**
- `--redis-url`: Redis URL for caching
- `--enable-cache`: Enable caching (true/false)

**Logging:**
- `--log-level`: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `--log-format`: Log format (json, text)

**Environment:**
- `--environment`: Environment (development, staging, production)
- `--debug`: Enable debug mode (true/false)

**Legacy Mode:**
- `--legacy`: Run V1 NLP-based implementation

**Other:**
- `--version`: Show version information
- `--help`: Show help message

## Sample Application

The included sample application demonstrates realistic UAT scenarios across multiple modules:

### Modules
1. **Login**: Email/password authentication with validation
2. **User Management**: CRUD operations with role assignment
3. **Dashboard**: User-specific statistics and navigation
4. **Profile**: View/edit user information and password change
5. **Settings**: Preferences and account management

### Test Credentials
- **Admin**: admin@example.com / Admin123!
- **User**: user@example.com / User123!

### Sample Stories

15+ comprehensive user stories are included in `uat-service/fixtures/sample-stories.json` covering:
- Positive flows (happy paths)
- Negative flows (validation errors)
- Edge cases (boundary conditions)
- Security scenarios (unauthorized access)

Load sample stories via the UI dropdown or API endpoint:
```bash
GET http://localhost:8000/api/sample-stories
```

## Project Structure

```
.
├── uat-service/                    # UAT automation service
│   ├── app/
│   │   ├── core/                   # Configuration, logging, exceptions
│   │   ├── models/                 # Pydantic data models
│   │   ├── services/               # Business logic services
│   │   │   ├── llm/                # LLM integration (Groq)
│   │   │   ├── parser/             # Story parsing & scenario generation
│   │   │   ├── executor/           # Test execution engine
│   │   │   ├── reporting/          # Report generation & analytics
│   │   │   └── storage/            # Database & file storage
│   │   ├── api/                    # REST API endpoints
│   │   │   └── v2/                 # V2 API routes
│   │   ├── templates/              # Jinja2 templates
│   │   └── main.py                 # FastAPI application
│   ├── archive/                    # Archived V1 POC code
│   │   └── v1-nlp-poc/
│   ├── fixtures/                   # Sample stories and test data
│   ├── tests/                      # Unit, integration, E2E tests
│   ├── artifacts/                  # Test results and reports
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── pyproject.toml
│   └── .env.example
├── sample-app/                     # Sample web application
│   ├── src/                        # React components
│   ├── public/                     # Static assets
│   ├── server.js                   # Node.js backend
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml              # Docker orchestration
├── MIGRATION.md                    # V1 to V2 migration guide
└── README.md                       # This file
```

## Migration from V1 to V2

### Key Differences

| Aspect | V1 (NLP POC) | V2 (LLM Production) |
|--------|--------------|---------------------|
| **Parsing** | spaCy NLP | Groq LLM with fallback |
| **Element Finding** | Simple CSS selectors | Multi-strategy with fuzzy matching |
| **Test Generation** | Rule-based | AI-generated scenarios |
| **Reporting** | Basic JSON | HTML/PDF with analytics |
| **Architecture** | Monolithic | Service-oriented |
| **Scalability** | Single-threaded | Parallel execution |
| **Error Handling** | Basic try-catch | Comprehensive with fallbacks |

### Migration Steps

1. **Archive V1 Code**: Existing code moved to `uat-service/archive/v1-nlp-poc/`
2. **Update Dependencies**: New requirements in `requirements.txt`
3. **Configure Environment**: Set `GROQ_API_KEY` in `.env`
4. **Update API Calls**: V2 API endpoints at `/api/v2/*`
5. **Test Migration**: Run sample stories to verify functionality

See `MIGRATION.md` for detailed migration guide.

### Legacy Mode

Run V1 code for comparison:
```bash
python -m app --legacy
```

This will load the archived V1 NLP-based implementation from `archive/v1-nlp-poc/` for backward compatibility testing and comparison purposes.

## Development

### Running Tests

```bash
cd uat-service

# Unit tests
pytest tests/unit -v

# Integration tests
pytest tests/integration -v

# E2E tests
pytest tests/e2e -v

# All tests with coverage
pytest --cov=app --cov-report=html
```

### Code Quality

```bash
# Linting
ruff check app/

# Type checking
mypy app/

# Formatting
black app/
```

### Hot Reload

Development mode with hot reload:
```bash
uvicorn app.main:app --reload --port 8000
```

## Deployment

### Docker Compose (Production)

```bash
# Build and start services
docker-compose up -d --build

# Scale UAT service
docker-compose up -d --scale uat-service=3

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Environment-Specific Configuration

```bash
# Development
ENVIRONMENT=development DEBUG=true docker-compose up

# Staging
ENVIRONMENT=staging docker-compose up

# Production
ENVIRONMENT=production DEBUG=false HEADLESS_MODE=true docker-compose up
```

### Health Checks

```bash
# Service health
curl http://localhost:8000/health

# Version info
curl http://localhost:8000/version
```

## Integrations

### Jira Integration

```bash
# Configure in .env
ENABLE_JIRA_INTEGRATION=true
JIRA_URL=https://your-domain.atlassian.net
JIRA_USERNAME=your-email@example.com
JIRA_API_TOKEN=your-api-token
```

### Azure DevOps Integration

```bash
# Configure in .env
ENABLE_AZURE_DEVOPS_INTEGRATION=true
AZURE_DEVOPS_ORG=your-org
AZURE_DEVOPS_PROJECT=your-project
AZURE_DEVOPS_PAT=your-personal-access-token
```

### Webhook Notifications

```bash
# Configure in .env
ENABLE_WEBHOOKS=true
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

## Troubleshooting

### Common Issues

#### 1. Groq API Key Not Set
```
Error: GROQ_API_KEY is required
Solution: Set GROQ_API_KEY in .env file
```

#### 2. Playwright Browsers Not Installed
```
Error: Executable doesn't exist at /path/to/chromium
Solution: Run `playwright install chromium`
```

#### 3. Sample App Not Accessible
```
Error: Connection refused to http://localhost:5173
Solution: Start sample app with `npm run dev`
```

#### 4. Redis Connection Failed
```
Error: Connection refused to redis://localhost:6379
Solution: Start Redis with `docker-compose up redis` or disable cache with ENABLE_CACHE=false
```

### Debug Mode

Enable debug logging:
```bash
LOG_LEVEL=DEBUG uvicorn app.main:app --reload
```

Run browser in headed mode:
```bash
HEADLESS_MODE=false SLOW_MO=1000 uvicorn app.main:app --reload
```

## Performance Optimization

### Caching

- **DOM Analysis**: Cached for 1 hour (configurable via `CACHE_DOM_TTL`)
- **LLM Responses**: Cached for 24 hours (configurable via `CACHE_LLM_TTL`)

### Parallel Execution

Adjust concurrency based on system resources:
```bash
# Low resources (1-2 parallel tests)
CONCURRENCY=1

# Medium resources (3-5 parallel tests)
CONCURRENCY=3

# High resources (6-10 parallel tests)
CONCURRENCY=10
```

### Database Optimization

For production, use PostgreSQL instead of SQLite:
```bash
DATABASE_URL=postgresql://user:password@localhost:5432/uat_service
```

## Security

### API Authentication

```bash
# Generate secure API key
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Configure in .env
API_KEYS=your-generated-key-1,your-generated-key-2

# Use in requests
curl -H "X-API-Key: your-generated-key-1" http://localhost:8000/api/v2/stories
```

### Rate Limiting

```bash
# Configure in .env
ENABLE_RATE_LIMITING=true
RATE_LIMIT_PER_MINUTE=60
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

[Your License Here]

## Support

- **Documentation**: See `/docs` directory
- **API Docs**: http://localhost:8000/docs
- **Issues**: [GitHub Issues](your-repo-url/issues)
- **Discussions**: [GitHub Discussions](your-repo-url/discussions)

## Roadmap

- [x] CLI support with environment overrides
- [ ] PDF report generation
- [ ] Mobile testing support (Appium)
- [ ] API testing capabilities
- [ ] Multi-tenant support
- [ ] Advanced analytics dashboard
- [ ] CI/CD pipeline templates
- [ ] Kubernetes deployment manifests

## Acknowledgments

- **Groq**: Free LLM API with Llama models
- **Playwright**: Browser automation framework
- **FastAPI**: Modern Python web framework
- **React**: Frontend library for sample app

---

**Version**: 2.0.0  
**Last Updated**: 2024  
**Status**: Production Ready
