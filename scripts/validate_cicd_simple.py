#!/usr/bin/env python3
"""
Simple CI/CD Configuration Validator for GOES_VFI

This script validates the CI/CD setup without external dependencies.
"""

from pathlib import Path
import sys


def validate_cicd_setup(repo_root: Path) -> bool:
    """Validate CI/CD setup and return True if successful."""
    print("🔧 GOES_VFI CI/CD Configuration Validator")
    print("=" * 50)

    errors = []
    warnings = []

    # Check GitHub Actions workflows
    print("📋 Checking GitHub Actions workflows...")
    workflows_dir = repo_root / ".github" / "workflows"

    if not workflows_dir.exists():
        errors.append("GitHub workflows directory (.github/workflows) not found")
    else:
        required_workflows = ["ci.yml", "cd.yml", "release.yml", "pr-quality.yml"]
        for workflow in required_workflows:
            workflow_path = workflows_dir / workflow
            if workflow_path.exists():
                print(f"  ✅ {workflow}")
            else:
                errors.append(f"Missing workflow: {workflow}")

    # Check Docker configuration
    print("🐳 Checking Docker configuration...")
    dockerfile = repo_root / "Dockerfile"
    if dockerfile.exists():
        print("  ✅ Dockerfile")
    else:
        errors.append("Dockerfile not found")

    compose_file = repo_root / "docker-compose.yml"
    if compose_file.exists():
        print("  ✅ docker-compose.yml")
    else:
        warnings.append("docker-compose.yml not found (optional)")

    # Check monitoring setup
    print("📊 Checking monitoring configuration...")
    monitoring_dir = repo_root / "monitoring"
    if monitoring_dir.exists():
        prometheus_config = monitoring_dir / "prometheus.yml"
        if prometheus_config.exists():
            print("  ✅ Prometheus configuration")
        else:
            warnings.append("Prometheus configuration not found")

        grafana_dir = monitoring_dir / "grafana"
        if grafana_dir.exists():
            print("  ✅ Grafana setup")
        else:
            warnings.append("Grafana setup not found")
    else:
        warnings.append("Monitoring directory not found (optional)")

    # Check required project files
    print("📁 Checking required project files...")
    required_files = [
        "pyproject.toml",
        "README.md",
    ]

    for file_name in required_files:
        file_path = repo_root / file_name
        if file_path.exists():
            print(f"  ✅ {file_name}")
        else:
            errors.append(f"Required file missing: {file_name}")

    # Check optional files
    optional_files = ["LICENSE", "CHANGELOG.md"]
    for file_name in optional_files:
        file_path = repo_root / file_name
        if file_path.exists():
            print(f"  ✅ {file_name}")
        else:
            warnings.append(f"Recommended file missing: {file_name}")

    # Report results
    print("\n" + "=" * 60)
    print("VALIDATION RESULTS")
    print("=" * 60)

    if errors:
        print(f"\n❌ ERRORS ({len(errors)}):")
        for error in errors:
            print(f"  • {error}")

    if warnings:
        print(f"\n⚠️  WARNINGS ({len(warnings)}):")
        for warning in warnings:
            print(f"  • {warning}")

    if not errors and not warnings:
        print("\n✅ All CI/CD configurations are valid!")
    elif not errors:
        print(f"\n✅ CI/CD setup is functional with {len(warnings)} warnings")
    else:
        print(f"\n❌ CI/CD setup has {len(errors)} errors that need to be fixed")

    print("\n" + "=" * 60)

    if not errors:
        print("\n🎉 CI/CD pipeline is ready for use!")
        print("\nNext steps:")
        print("1. Set up GitHub repository secrets for deployment")
        print("2. Test workflows by creating a pull request")
        print("3. Configure monitoring dashboards")
        print("4. Set up release process")
        return True
    print("\n💡 Please fix the errors above before using CI/CD")
    return False


def main() -> int:
    """Main function."""
    repo_root = Path(__file__).parent.parent
    success = validate_cicd_setup(repo_root)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
