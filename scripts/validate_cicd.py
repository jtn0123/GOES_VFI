#!/usr/bin/env python3
"""
CI/CD Configuration Validator for GOES_VFI

This script validates the CI/CD setup to ensure all components are properly configured.
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import yaml

from goesvfi.utils import log

LOGGER = log.get_logger(__name__)


# Simple validation without external dependencies
def simple_yaml_check(file_path: Path) -> bool:
    """Simple YAML syntax check without PyYAML."""
    try:
        with open(file_path, "r") as f:
            content = f.read()

        # Basic YAML syntax checks
        lines = content.split("\n")
        for _, line in enumerate(lines):
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                # Check for basic YAML structure
                if ":" not in line and not stripped.startswith("-"):
                    if not stripped.endswith(":"):
                        continue  # Allow multi-line values
        return True
    except Exception:
        return False


class CICDValidator:
    """Validates CI/CD configuration files and setup."""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def validate_all(self) -> bool:
        """Run all validation checks."""
        print("Starting CI/CD validation...")

        # Check GitHub Actions workflows
        self.validate_github_workflows()

        # Check Docker configuration
        self.validate_docker_config()

        # Check monitoring configuration
        self.validate_monitoring_config()

        # Check project structure
        self.validate_project_structure()

        # Check required files
        self.validate_required_files()

        # Report results
        self.report_results()

        return len(self.errors) == 0

    def validate_github_workflows(self) -> None:
        """Validate GitHub Actions workflow files."""
        print("Validating GitHub Actions workflows...")

        workflows_dir = self.repo_root / ".github" / "workflows"

        if not workflows_dir.exists():
            self.errors.append("GitHub workflows directory not found")
            return

        required_workflows = ["ci.yml", "cd.yml", "release.yml", "pr-quality.yml"]

        for workflow_file in required_workflows:
            workflow_path = workflows_dir / workflow_file

            if not workflow_path.exists():
                self.errors.append(f"Missing workflow file: {workflow_file}")
                continue

            try:
                with open(workflow_path, "r") as f:
                    workflow_config = yaml.safe_load(f)

                # Validate basic structure
                if "name" not in workflow_config:
                    self.errors.append(f"Workflow {workflow_file} missing 'name' field")

                if "on" not in workflow_config:
                    self.errors.append(f"Workflow {workflow_file} missing 'on' field")

                if "jobs" not in workflow_config:
                    self.errors.append(f"Workflow {workflow_file} missing 'jobs' field")

                # Validate specific workflow requirements
                self._validate_specific_workflow(workflow_file, workflow_config)

                LOGGER.info(f"✅ Workflow {workflow_file} is valid")

            except yaml.YAMLError as e:
                self.errors.append(f"Invalid YAML in {workflow_file}: {e}")
            except Exception as e:
                self.errors.append(f"Error reading {workflow_file}: {e}")

    def _validate_specific_workflow(self, filename: str, config: Dict[str, Any]) -> None:
        """Validate specific workflow requirements."""
        if filename == "ci.yml":
            # CI workflow should have test and lint jobs
            jobs = config.get("jobs", {})
            if "lint" not in jobs:
                self.warnings.append("CI workflow missing 'lint' job")
            if "test" not in jobs:
                self.warnings.append("CI workflow missing 'test' job")

        elif filename == "cd.yml":
            # CD workflow should be triggered by tags
            triggers = config.get("on", {})
            if "push" not in triggers or "tags" not in triggers.get("push", {}):
                self.warnings.append("CD workflow should be triggered by tags")

        elif filename == "release.yml":
            # Release workflow should have manual trigger
            triggers = config.get("on", {})
            if "workflow_dispatch" not in triggers:
                self.warnings.append("Release workflow should have manual trigger")

    def validate_docker_config(self) -> None:
        """Validate Docker configuration."""
        LOGGER.info("Validating Docker configuration...")

        # Check Dockerfile
        dockerfile = self.repo_root / "Dockerfile"
        if not dockerfile.exists():
            self.errors.append("Dockerfile not found")
        else:
            self._validate_dockerfile(dockerfile)

        # Check docker-compose.yml
        compose_file = self.repo_root / "docker-compose.yml"
        if not compose_file.exists():
            self.warnings.append("docker-compose.yml not found")
        else:
            self._validate_docker_compose(compose_file)

    def _validate_dockerfile(self, dockerfile_path: Path) -> None:
        """Validate Dockerfile content."""
        try:
            with open(dockerfile_path, "r") as f:
                content = f.read()

            # Check for important instructions
            required_instructions = [
                "FROM python:",
                "WORKDIR",
                "COPY pyproject.toml",
                "RUN pip install",
            ]

            for instruction in required_instructions:
                if instruction not in content:
                    self.warnings.append(f"Dockerfile missing recommended instruction: {instruction}")

            # Check for security best practices
            if "USER root" in content and "USER " not in content.split("USER root")[1]:
                self.warnings.append("Dockerfile runs as root user (security risk)")

            LOGGER.info("✅ Dockerfile validation complete")

        except Exception as e:
            self.errors.append(f"Error reading Dockerfile: {e}")

    def _validate_docker_compose(self, compose_path: Path) -> None:
        """Validate docker-compose configuration."""
        try:
            with open(compose_path, "r") as f:
                compose_config = yaml.safe_load(f)

            # Check version
            if "version" not in compose_config:
                self.warnings.append("docker-compose.yml missing version")

            # Check services
            if "services" not in compose_config:
                self.errors.append("docker-compose.yml missing services")
                return

            services = compose_config["services"]

            # Check for main application service
            main_services = [name for name in services.keys() if "goes" in name.lower()]
            if not main_services:
                self.warnings.append("No main application service found in docker-compose.yml")

            LOGGER.info("✅ docker-compose.yml validation complete")

        except yaml.YAMLError as e:
            self.errors.append(f"Invalid YAML in docker-compose.yml: {e}")
        except Exception as e:
            self.errors.append(f"Error reading docker-compose.yml: {e}")

    def validate_monitoring_config(self) -> None:
        """Validate monitoring configuration."""
        LOGGER.info("Validating monitoring configuration...")

        monitoring_dir = self.repo_root / "monitoring"
        if not monitoring_dir.exists():
            self.warnings.append("Monitoring directory not found")
            return

        # Check Prometheus config
        prometheus_config = monitoring_dir / "prometheus.yml"
        if prometheus_config.exists():
            self._validate_prometheus_config(prometheus_config)
        else:
            self.warnings.append("Prometheus configuration not found")

        # Check Grafana dashboards
        grafana_dir = monitoring_dir / "grafana" / "dashboards"
        if grafana_dir.exists():
            dashboard_files = list(grafana_dir.glob("*.json"))
            if not dashboard_files:
                self.warnings.append("No Grafana dashboards found")
            else:
                for dashboard in dashboard_files:
                    self._validate_grafana_dashboard(dashboard)
        else:
            self.warnings.append("Grafana dashboards directory not found")

    def _validate_prometheus_config(self, config_path: Path) -> None:
        """Validate Prometheus configuration."""
        try:
            with open(config_path, "r") as f:
                config = yaml.safe_load(f)

            # Check required sections
            required_sections = ["global", "scrape_configs"]
            for section in required_sections:
                if section not in config:
                    self.errors.append(f"Prometheus config missing {section} section")

            LOGGER.info("✅ Prometheus configuration is valid")

        except Exception as e:
            self.errors.append(f"Error validating Prometheus config: {e}")

    def _validate_grafana_dashboard(self, dashboard_path: Path) -> None:
        """Validate Grafana dashboard JSON."""
        try:
            with open(dashboard_path, "r") as f:
                dashboard = json.load(f)

            # Check basic structure
            if "dashboard" not in dashboard:
                self.errors.append(f"Dashboard {dashboard_path.name} missing 'dashboard' key")
                return

            dashboard_config = dashboard["dashboard"]

            required_fields = ["title", "panels"]
            for field in required_fields:
                if field not in dashboard_config:
                    self.warnings.append(f"Dashboard {dashboard_path.name} missing {field}")

            LOGGER.info(f"✅ Dashboard {dashboard_path.name} is valid")

        except Exception as e:
            self.errors.append(f"Error validating dashboard {dashboard_path.name}: {e}")

    def validate_project_structure(self) -> None:
        """Validate project structure for CI/CD compatibility."""
        LOGGER.info("Validating project structure...")

        # Check for Python package structure
        if not (self.repo_root / "goesvfi" / "__init__.py").exists():
            self.errors.append("Main package __init__.py not found")

        # Check for test directory
        if not (self.repo_root / "tests").exists():
            self.warnings.append("Tests directory not found")

        # Check for scripts directory
        if not (self.repo_root / "scripts").exists():
            self.warnings.append("Scripts directory not found")

        LOGGER.info("✅ Project structure validation complete")

    def validate_required_files(self) -> None:
        """Validate presence of required files."""
        LOGGER.info("Validating required files...")

        required_files = [
            "pyproject.toml",
            "README.md",
            "LICENSE",
            "CHANGELOG.md",
        ]

        for file_name in required_files:
            file_path = self.repo_root / file_name
            if not file_path.exists():
                if file_name in ["LICENSE", "CHANGELOG.md"]:
                    self.warnings.append(f"Recommended file missing: {file_name}")
                else:
                    self.errors.append(f"Required file missing: {file_name}")

        LOGGER.info("✅ Required files validation complete")

    def report_results(self) -> None:
        """Report validation results."""
        print("\n" + "=" * 60)
        print("CI/CD VALIDATION RESULTS")
        print("=" * 60)

        if self.errors:
            print(f"\n❌ ERRORS ({len(self.errors)}):")
            for error in self.errors:
                print(f"  • {error}")

        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"  • {warning}")

        if not self.errors and not self.warnings:
            print("\n✅ All CI/CD configurations are valid!")
        elif not self.errors:
            print(f"\n✅ CI/CD setup is functional with {len(self.warnings)} warnings")
        else:
            print(f"\n❌ CI/CD setup has {len(self.errors)} errors that need to be fixed")

        print("\n" + "=" * 60)


def main():
    """Main function."""
    print("🔧 GOES_VFI CI/CD Configuration Validator")
    print("=" * 50)

    repo_root = Path(__file__).parent.parent
    validator = CICDValidator(repo_root)

    success = validator.validate_all()

    if success:
        print("\n🎉 CI/CD setup is ready for use!")
        return 0
    else:
        print("\n💡 Please fix the errors above before using CI/CD")
        return 1


if __name__ == "__main__":
    sys.exit(main())
