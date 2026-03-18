#!/usr/bin/env python3
"""
Production Readiness Check for MCP Server

Comprehensive checklist for production deployment:
- Configuration validation
- Security checks
- Error handling verification
- Logging configuration
- Performance considerations
- Documentation completeness
- Dependency verification
- Test coverage
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, List, Tuple
import importlib.util

# Color codes for terminal output
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"

CHECK_PASS = f"{GREEN}✓{RESET}"
CHECK_WARN = f"{YELLOW}⚠{RESET}"
CHECK_FAIL = f"{RED}✗{RESET}"


class ProductionReadinessChecker:
    """Comprehensive production readiness checker."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.issues: List[Tuple[str, str, str]] = []  # (category, check, status)
        self.warnings: List[Tuple[str, str, str]] = []
        self.passed: List[Tuple[str, str]] = []

    def check(self) -> Dict[str, any]:
        """Run all production readiness checks."""
        print(f"{BOLD}{BLUE}=== Production Readiness Check ==={RESET}\n")

        self.check_configuration()
        self.check_security()
        self.check_error_handling()
        self.check_logging()
        self.check_performance()
        self.check_monitoring()
        self.check_documentation()
        self.check_dependencies()
        self.check_tests()
        self.check_deployment()

        return self.generate_report()

    def check_configuration(self):
        """Check configuration management."""
        print(f"{BOLD}1. Configuration Management{RESET}")
        
        # Check .env file exists
        env_file = self.project_root / ".env"
        if env_file.exists():
            self.passed.append(("Configuration", ".env file exists"))
            print(f"  {CHECK_PASS} .env file exists")
        else:
            self.issues.append(("Configuration", ".env file missing", "error"))
            print(f"  {CHECK_FAIL} .env file missing")

        # Check .env.example exists
        env_example = self.project_root / ".env.example"
        if env_example.exists():
            self.passed.append(("Configuration", ".env.example exists"))
            print(f"  {CHECK_PASS} .env.example exists")
        else:
            self.warnings.append(("Configuration", ".env.example missing", "warning"))
            print(f"  {CHECK_WARN} .env.example missing")

        # Check config module
        config_file = self.project_root / "aiecs" / "mcp" / "config.py"
        if config_file.exists():
            self.passed.append(("Configuration", "Config module exists"))
            print(f"  {CHECK_PASS} Config module exists")
        else:
            self.issues.append(("Configuration", "Config module missing", "error"))
            print(f"  {CHECK_FAIL} Config module missing")

        # Check environment variable loading
        try:
            from aiecs.config import load_env_files
            load_env_files()
            self.passed.append(("Configuration", "Environment loading works"))
            print(f"  {CHECK_PASS} Environment variable loading works")
        except Exception as e:
            self.issues.append(("Configuration", f"Environment loading failed: {e}", "error"))
            print(f"  {CHECK_FAIL} Environment variable loading failed: {e}")

        print()

    def check_security(self):
        """Check security measures."""
        print(f"{BOLD}2. Security{RESET}")

        # Check security module
        security_file = self.project_root / "aiecs" / "mcp" / "security.py"
        if security_file.exists():
            self.passed.append(("Security", "Security module exists"))
            print(f"  {CHECK_PASS} Security module exists")
            
            # Check for sanitization functions
            with open(security_file) as f:
                content = f.read()
                if "sanitize_error_message" in content:
                    self.passed.append(("Security", "Error sanitization implemented"))
                    print(f"  {CHECK_PASS} Error sanitization implemented")
                else:
                    self.warnings.append(("Security", "Error sanitization missing", "warning"))
                    print(f"  {CHECK_WARN} Error sanitization missing")
        else:
            self.issues.append(("Security", "Security module missing", "error"))
            print(f"  {CHECK_FAIL} Security module missing")

        # Check API key redaction
        try:
            from aiecs.mcp.security import sanitize_error_message
            test_msg = "API key abc123def456 is invalid"
            sanitized = sanitize_error_message(test_msg, redact_api_keys=True)
            if "REDACTED" in sanitized or "abc123" not in sanitized:
                self.passed.append(("Security", "API key redaction works"))
                print(f"  {CHECK_PASS} API key redaction works")
            else:
                self.warnings.append(("Security", "API key redaction may not work", "warning"))
                print(f"  {CHECK_WARN} API key redaction may not work")
        except Exception as e:
            self.warnings.append(("Security", f"API key redaction check failed: {e}", "warning"))
            print(f"  {CHECK_WARN} API key redaction check failed: {e}")

        # Check CORS configuration
        main_mcp_file = self.project_root / "aiecs" / "main_mcp.py"
        if main_mcp_file.exists():
            with open(main_mcp_file) as f:
                content = f.read()
                if "CORSMiddleware" in content:
                    self.passed.append(("Security", "CORS middleware configured"))
                    print(f"  {CHECK_PASS} CORS middleware configured")
                else:
                    self.warnings.append(("Security", "CORS middleware not configured", "warning"))
                    print(f"  {CHECK_WARN} CORS middleware not configured")

        print()

    def check_error_handling(self):
        """Check error handling."""
        print(f"{BOLD}3. Error Handling{RESET}")

        # Check error handling in main_mcp.py
        main_mcp_file = self.project_root / "aiecs" / "main_mcp.py"
        if main_mcp_file.exists():
            with open(main_mcp_file) as f:
                content = f.read()
                error_count = content.count("except")
                logger_error_count = content.count("logger.error")
                
                if error_count > 0:
                    self.passed.append(("Error Handling", f"Error handling present ({error_count} try/except blocks)"))
                    print(f"  {CHECK_PASS} Error handling present ({error_count} try/except blocks)")
                else:
                    self.warnings.append(("Error Handling", "No error handling found", "warning"))
                    print(f"  {CHECK_WARN} No error handling found")

                if logger_error_count > 0:
                    self.passed.append(("Error Handling", f"Error logging present ({logger_error_count} logger.error calls)"))
                    print(f"  {CHECK_PASS} Error logging present")
                else:
                    self.warnings.append(("Error Handling", "Error logging missing", "warning"))
                    print(f"  {CHECK_WARN} Error logging missing")

        # Check tool adapter error handling
        tool_adapter_file = self.project_root / "aiecs" / "mcp" / "placeholder_adapter.py"
        if tool_adapter_file.exists():
            with open(tool_adapter_file) as f:
                content = f.read()
                if "isError" in content or "is_error" in content:
                    self.passed.append(("Error Handling", "MCP error format implemented"))
                    print(f"  {CHECK_PASS} MCP error format implemented")
                else:
                    self.warnings.append(("Error Handling", "MCP error format missing", "warning"))
                    print(f"  {CHECK_WARN} MCP error format missing")

        print()

    def check_logging(self):
        """Check logging configuration."""
        print(f"{BOLD}4. Logging{RESET}")

        main_mcp_file = self.project_root / "aiecs" / "main_mcp.py"
        if main_mcp_file.exists():
            with open(main_mcp_file) as f:
                content = f.read()
                if "logging.basicConfig" in content or "logging.getLogger" in content:
                    self.passed.append(("Logging", "Logging configured"))
                    print(f"  {CHECK_PASS} Logging configured")
                else:
                    self.warnings.append(("Logging", "Logging not configured", "warning"))
                    print(f"  {CHECK_WARN} Logging not configured")

                logger_calls = content.count("logger.")
                if logger_calls > 10:
                    self.passed.append(("Logging", f"Comprehensive logging ({logger_calls} logger calls)"))
                    print(f"  {CHECK_PASS} Comprehensive logging ({logger_calls} logger calls)")
                elif logger_calls > 0:
                    self.warnings.append(("Logging", f"Limited logging ({logger_calls} logger calls)", "warning"))
                    print(f"  {CHECK_WARN} Limited logging ({logger_calls} logger calls)")
                else:
                    self.issues.append(("Logging", "No logging calls found", "error"))
                    print(f"  {CHECK_FAIL} No logging calls found")

        print()

    def check_performance(self):
        """Check performance optimizations."""
        print(f"{BOLD}5. Performance{RESET}")

        # Check throttling
        throttling_file = self.project_root / "aiecs" / "mcp" / "throttling_middleware.py"
        if throttling_file.exists():
            self.passed.append(("Performance", "Throttling middleware exists"))
            print(f"  {CHECK_PASS} Throttling middleware exists")
        else:
            self.warnings.append(("Performance", "Throttling middleware missing", "warning"))
            print(f"  {CHECK_WARN} Throttling middleware missing")

        # Check concurrency control
        concurrency_file = self.project_root / "aiecs" / "mcp" / "concurrency.py"
        if concurrency_file.exists():
            self.passed.append(("Performance", "Concurrency control exists"))
            print(f"  {CHECK_PASS} Concurrency control exists")
        else:
            self.warnings.append(("Performance", "Concurrency control missing", "warning"))
            print(f"  {CHECK_WARN} Concurrency control missing")

        # Check caching
        try:
            from aiecs.infrastructure.persistence import get_redis_client
            self.passed.append(("Performance", "Redis caching available"))
            print(f"  {CHECK_PASS} Redis caching available")
        except:
            self.warnings.append(("Performance", "Redis caching optional (graceful degradation)", "warning"))
            print(f"  {CHECK_WARN} Redis caching optional (graceful degradation)")

        print()

    def check_monitoring(self):
        """Check monitoring and health checks."""
        print(f"{BOLD}6. Monitoring & Health Checks{RESET}")

        main_mcp_file = self.project_root / "aiecs" / "main_mcp.py"
        if main_mcp_file.exists():
            with open(main_mcp_file) as f:
                content = f.read()
                if "/health" in content:
                    self.passed.append(("Monitoring", "Health check endpoint exists"))
                    print(f"  {CHECK_PASS} Health check endpoint exists")
                else:
                    self.issues.append(("Monitoring", "Health check endpoint missing", "error"))
                    print(f"  {CHECK_FAIL} Health check endpoint missing")
                if "tools" in content and "health" in content.lower():
                    self.passed.append(("Monitoring", "Health check includes tool status"))
                    print(f"  {CHECK_PASS} Health check includes tool status")

        print()

    def check_documentation(self):
        """Check documentation completeness."""
        print(f"{BOLD}7. Documentation{RESET}")

        readme_file = self.project_root / "README.md"
        if readme_file.exists():
            self.passed.append(("Documentation", "README.md exists"))
            print(f"  {CHECK_PASS} README.md exists")
            
            with open(readme_file) as f:
                content = f.read()
                if len(content) > 1000:
                    self.passed.append(("Documentation", "README.md is comprehensive"))
                    print(f"  {CHECK_PASS} README.md is comprehensive")
                else:
                    self.warnings.append(("Documentation", "README.md is brief", "warning"))
                    print(f"  {CHECK_WARN} README.md is brief")
        else:
            self.issues.append(("Documentation", "README.md missing", "error"))
            print(f"  {CHECK_FAIL} README.md missing")

        # Check MCP README
        mcp_readme = self.project_root / "aiecs" / "mcp" / "README.md"
        if mcp_readme.exists():
            self.passed.append(("Documentation", "MCP README exists"))
            print(f"  {CHECK_PASS} MCP README exists")
        else:
            self.warnings.append(("Documentation", "MCP README missing", "warning"))
            print(f"  {CHECK_WARN} MCP README missing")

        print()

    def check_dependencies(self):
        """Check dependencies."""
        print(f"{BOLD}8. Dependencies{RESET}")

        pyproject_file = self.project_root / "pyproject.toml"
        if pyproject_file.exists():
            self.passed.append(("Dependencies", "pyproject.toml exists"))
            print(f"  {CHECK_PASS} pyproject.toml exists")
            
            # Check critical dependencies
            with open(pyproject_file) as f:
                content = f.read()
                critical_deps = ["fastapi", "fastmcp", "uvicorn", "pydantic"]
                for dep in critical_deps:
                    if dep in content.lower():
                        self.passed.append(("Dependencies", f"{dep} dependency present"))
                        print(f"  {CHECK_PASS} {dep} dependency present")
                    else:
                        self.issues.append(("Dependencies", f"{dep} dependency missing", "error"))
                        print(f"  {CHECK_FAIL} {dep} dependency missing")
        else:
            self.issues.append(("Dependencies", "pyproject.toml missing", "error"))
            print(f"  {CHECK_FAIL} pyproject.toml missing")

        print()

    def check_tests(self):
        """Check test coverage."""
        print(f"{BOLD}9. Tests{RESET}")

        tests_dir = self.project_root / "tests" / "mcp"
        if tests_dir.exists():
            test_files = list(tests_dir.glob("test_*.py"))
            if test_files:
                self.passed.append(("Tests", f"{len(test_files)} test files found"))
                print(f"  {CHECK_PASS} {len(test_files)} test files found")
            else:
                self.warnings.append(("Tests", "No test files found", "warning"))
                print(f"  {CHECK_WARN} No test files found")
        else:
            self.warnings.append(("Tests", "Tests directory missing", "warning"))
            print(f"  {CHECK_WARN} Tests directory missing")

        # Check office tool integration tests
        office_tests = [
            self.project_root / "tests" / "mcp" / "test_office_execute_builder.py",
            self.project_root / "tests" / "mcp" / "test_office_tool_adapter.py",
        ]
        if any(t.exists() for t in office_tests):
            self.passed.append(("Tests", "Office tool tests exist"))
            print(f"  {CHECK_PASS} Office tool tests exist")
        else:
            self.warnings.append(("Tests", "Office tool tests missing", "warning"))
            print(f"  {CHECK_WARN} Office tool tests missing")

        print()

    def check_deployment(self):
        """Check deployment readiness."""
        print(f"{BOLD}10. Deployment{RESET}")

        # Check Dockerfile
        dockerfile = self.project_root / "Dockerfile.mcp"
        if dockerfile.exists():
            self.passed.append(("Deployment", "Dockerfile.mcp exists"))
            print(f"  {CHECK_PASS} Dockerfile.mcp exists")
        else:
            self.warnings.append(("Deployment", "Dockerfile.mcp missing", "warning"))
            print(f"  {CHECK_WARN} Dockerfile.mcp missing")

        # Check docker-compose
        docker_compose = self.project_root / "docker-compose.mcp.yml"
        if docker_compose.exists():
            self.passed.append(("Deployment", "docker-compose.mcp.yml exists"))
            print(f"  {CHECK_PASS} docker-compose.mcp.yml exists")
        else:
            self.warnings.append(("Deployment", "docker-compose.mcp.yml missing", "warning"))
            print(f"  {CHECK_WARN} docker-compose.mcp.yml missing")

        print()

    def generate_report(self) -> Dict[str, any]:
        """Generate final report."""
        total_checks = len(self.passed) + len(self.warnings) + len(self.issues)
        passed_count = len(self.passed)
        warning_count = len(self.warnings)
        error_count = len(self.issues)

        print(f"\n{BOLD}{BLUE}=== Summary ==={RESET}\n")
        print(f"Total Checks: {total_checks}")
        print(f"{GREEN}Passed: {passed_count}{RESET}")
        print(f"{YELLOW}Warnings: {warning_count}{RESET}")
        print(f"{RED}Errors: {error_count}{RESET}\n")

        if error_count == 0 and warning_count == 0:
            print(f"{BOLD}{GREEN}✓ Production Ready!{RESET}\n")
        elif error_count == 0:
            print(f"{BOLD}{YELLOW}⚠ Production Ready with Warnings{RESET}\n")
        else:
            print(f"{BOLD}{RED}✗ Not Production Ready{RESET}\n")
            print("Please fix the following errors:\n")
            for category, check, status in self.issues:
                print(f"  {RED}✗{RESET} [{category}] {check}")

        return {
            "total": total_checks,
            "passed": passed_count,
            "warning_count": warning_count,
            "error_count": error_count,
            "issues": self.issues,
            "warnings": self.warnings,
            "passed": self.passed,
        }


def main():
    """Main entry point."""
    project_root = Path(__file__).parent.parent
    checker = ProductionReadinessChecker(project_root)
    report = checker.check()
    
    # Exit with error code if there are critical issues
    if report["error_count"] > 0:
        sys.exit(1)
    elif report["warning_count"] > 0:
        sys.exit(0)  # Warnings are acceptable
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
