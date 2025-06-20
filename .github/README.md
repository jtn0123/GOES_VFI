# GOES_VFI CI/CD Pipeline

This directory contains the complete CI/CD (Continuous Integration/Continuous Deployment) setup for GOES_VFI, providing automated testing, quality assurance, security scanning, and deployment processes.

## 🔄 Workflows Overview

### Core Workflows

#### 1. **CI Pipeline** (`ci.yml`)
Main continuous integration pipeline that runs on every push and pull request.

**Jobs:**
- **Lint**: Code quality checks with comprehensive linting tools
- **Test**: Multi-platform testing (Ubuntu, Windows, macOS) with Python 3.13
- **Build**: Package building and validation
- **Docs**: Documentation generation and deployment
- **Security Scan**: Vulnerability scanning with Trivy
- **Dependency Review**: Automated dependency security review

**Triggers:**
- Push to `main` or `develop` branches
- Pull requests to `main` or `develop` branches

#### 2. **CD Pipeline** (`cd.yml`)
Continuous deployment pipeline for releases.

**Jobs:**
- **Deploy PyPI**: Automated package publishing to PyPI/Test PyPI
- **Create Release Artifacts**: Cross-platform executable builds
- **Deploy Docs**: Documentation deployment to GitHub Pages
- **Docker Build/Push**: Container image building and registry publishing
- **Notify Deployment**: Status notifications and summaries

**Triggers:**
- Git tags matching `v*` pattern
- Published releases

#### 3. **Release Pipeline** (`release.yml`)
Automated release management workflow.

**Features:**
- Version validation and format checking
- Automated version bumping in project files
- Changelog generation
- GitHub release creation
- Triggering of CD pipeline

**Trigger:**
- Manual workflow dispatch with version input

#### 4. **PR Quality Checks** (`pr-quality.yml`)
Comprehensive quality analysis for pull requests.

**Checks:**
- PR title and description validation
- Code quality analysis on changed files only
- Security scanning for new vulnerabilities
- Performance benchmarking
- Documentation coverage verification
- Automated PR status comments

## 🐳 Containerization

### Docker Setup

The project includes comprehensive Docker support:

- **`Dockerfile`**: Multi-stage container build with Python 3.13
- **`docker-compose.yml`**: Complete development environment with:
  - GOES_VFI application
  - Redis cache
  - PostgreSQL database
  - Prometheus monitoring
  - Grafana dashboards
  - Jupyter notebooks

### Container Features

- **GUI Support**: X11 forwarding for Linux GUI applications
- **Volume Mounting**: Development code and data persistence
- **Health Checks**: Built-in container health monitoring
- **Multi-arch Support**: Builds for multiple architectures
- **Security**: Non-root user execution
- **Optimized**: Multi-stage builds for smaller images

## 📊 Monitoring & Observability

### Prometheus Metrics

The application exposes metrics for monitoring:

```
# Application metrics
goes_vfi_requests_total
goes_vfi_errors_total
goes_vfi_processing_duration_seconds
goes_vfi_processing_queue_size
goes_vfi_memory_usage_bytes
```

### Grafana Dashboards

Pre-configured dashboards monitor:
- Application health and uptime
- Resource usage (CPU, memory, disk)
- Processing performance metrics
- Error rates and trends
- Queue backlogs

### Alerting Rules

Automated alerts for:
- Application downtime
- High resource usage
- Processing queue backlogs
- High error rates
- Infrastructure failures

## 🔧 Setup Instructions

### Prerequisites

1. **GitHub Repository Secrets** (for full CD functionality):
   ```
   PYPI_API_TOKEN          # PyPI publishing
   TEST_PYPI_API_TOKEN     # Test PyPI publishing
   DOCKERHUB_USERNAME      # Docker Hub publishing
   DOCKERHUB_TOKEN         # Docker Hub authentication
   SLACK_WEBHOOK_URL       # Slack notifications (optional)
   ```

2. **Local Development**:
   ```bash
   # Clone repository
   git clone https://github.com/username/GOES_VFI.git
   cd GOES_VFI

   # Install dependencies
   pip install -r requirements.txt
   pip install -r test-requirements.txt
   ```

### Running CI/CD Locally

#### Docker Development Environment
```bash
# Start full development stack
docker-compose up -d

# View logs
docker-compose logs -f goes-vfi

# Stop stack
docker-compose down
```

#### Manual Testing
```bash
# Run linting
python run_linters.py --check

# Run type checking
python run_mypy_checks.py

# Run tests
python run_working_tests_with_mocks.py

# Build documentation
python scripts/generate_docs.py --build
```

## 🚀 Deployment Process

### Automated Release Process

1. **Create Release**:
   ```bash
   # Via GitHub UI: Actions → Release → Run workflow
   # Input version: v1.0.0
   ```

2. **Automated Steps**:
   - Version validation and conflict checking
   - Full test suite execution
   - Version file updates (pyproject.toml, __init__.py)
   - Changelog generation
   - Git tag creation
   - GitHub release creation
   - CD pipeline triggering

3. **CD Pipeline Execution**:
   - PyPI package publishing
   - Cross-platform executable creation
   - Docker image building and publishing
   - Documentation deployment
   - Status notifications

### Manual Deployment

#### PyPI Publishing
```bash
# Build package
python -m build

# Upload to Test PyPI
twine upload --repository testpypi dist/*

# Upload to PyPI
twine upload dist/*
```

#### Docker Publishing
```bash
# Build image
docker build -t goesvfi/goes-vfi:latest .

# Push to registry
docker push goesvfi/goes-vfi:latest
```

## 📈 Quality Gates

### Code Quality Standards

All code must pass:
- **Flake8**: Style and error checking
- **MyPy**: Type checking in strict mode
- **Pylint**: Advanced static analysis
- **Black**: Code formatting (enforced)
- **isort**: Import sorting

### Security Requirements

- **Bandit**: Python security linting
- **Safety**: Dependency vulnerability scanning
- **Trivy**: Container vulnerability scanning
- **Semgrep**: Security pattern matching

### Test Coverage

- **Minimum Coverage**: 80% (tracked via Codecov)
- **Platform Testing**: Ubuntu, Windows, macOS
- **Python Versions**: 3.13

## 🔍 Monitoring Integration

### Application Metrics

Add to your application:

```python
from prometheus_client import Counter, Histogram, Gauge

# Request metrics
REQUEST_COUNT = Counter('goes_vfi_requests_total', 'Total requests')
ERROR_COUNT = Counter('goes_vfi_errors_total', 'Total errors')

# Processing metrics
PROCESSING_TIME = Histogram('goes_vfi_processing_duration_seconds', 'Processing time')
QUEUE_SIZE = Gauge('goes_vfi_processing_queue_size', 'Queue size')
```

### Health Checks

Implement health check endpoint:

```python
@app.route('/health')
def health_check():
    return {'status': 'healthy', 'timestamp': time.time()}
```

## 🛠 Troubleshooting

### Common Issues

#### CI Pipeline Failures
```bash
# Check logs in GitHub Actions
# Common fixes:
- Update dependencies in requirements.txt
- Fix linting issues: python run_linters.py --format
- Resolve test failures: python run_working_tests_with_mocks.py
```

#### Docker Build Issues
```bash
# Local debugging
docker build --no-cache -t goes-vfi-debug .
docker run -it goes-vfi-debug /bin/bash
```

#### Release Pipeline Problems
```bash
# Check version format: must be v1.0.0 format
# Ensure no existing tag conflicts
# Verify all tests pass locally first
```

### Performance Optimization

#### Pipeline Speed
- Dependency caching (implemented)
- Parallel job execution (implemented)
- Selective testing (PR quality checks)
- Multi-stage Docker builds (implemented)

#### Resource Usage
- Container resource limits
- Prometheus monitoring
- Automated scaling (in docker-compose)

## 📚 Additional Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Docker Documentation](https://docs.docker.com/)
- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)

## 🤝 Contributing

When contributing to CI/CD:

1. Test changes locally with act: `act -j build`
2. Update documentation for new workflows
3. Follow conventional commit format
4. Add appropriate monitoring for new features

## 📝 License

This CI/CD setup is part of GOES_VFI and follows the same MIT license.
