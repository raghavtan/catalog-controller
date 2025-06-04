#!/usr/bin/env python
"""
Run all tests with proper configuration and generate coverage report.

This script ensures that all tests are properly discovered and run
with the correct asyncio configuration.
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path

# Colors for terminal output
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
RESET = "\033[0m"


def print_header(message):
    """Print a formatted header message."""
    print(f"\n{BLUE}{'=' * 80}{RESET}")
    print(f"{BLUE}= {message}{RESET}")
    print(f"{BLUE}{'=' * 80}{RESET}\n")


def print_success(message):
    """Print a success message."""
    print(f"{GREEN}{message}{RESET}")


def print_warning(message):
    """Print a warning message."""
    print(f"{YELLOW}{message}{RESET}")


def print_error(message):
    """Print an error message."""
    print(f"{RED}{message}{RESET}")


def run_command(command, capture_output=True):
    """Run a shell command and return the result."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            check=False,
            capture_output=capture_output,
            text=True
        )
        return result
    except subprocess.SubprocessError as e:
        print_error(f"Command failed: {command}")
        print_error(f"Error: {e}")
        return None


def create_test_directories():
    """Create test directories if they don't exist."""
    Path("tests/unit").mkdir(parents=True, exist_ok=True)
    Path("tests/integration").mkdir(parents=True, exist_ok=True)


def main():
    """Main function to run tests."""
    parser = argparse.ArgumentParser(description="Run tests for the catalog controller")
    parser.add_argument("--unit", action="store_true", help="Run only unit tests")
    parser.add_argument("--integration", action="store_true", help="Run only integration tests")
    parser.add_argument("--e2e", action="store_true", help="Run only end-to-end tests")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show verbose output")
    parser.add_argument("--coverage", action="store_true", help="Generate coverage report")
    parser.add_argument("--html", action="store_true", help="Generate HTML coverage report")
    parser.add_argument("--file", type=str, help="Run tests from a specific file")
    parser.add_argument("--pattern", type=str, help="Run tests matching a pattern")

    args = parser.parse_args()

    # Check Python environment
    print_header("Checking Python environment")
    python_version = sys.version.split()[0]
    print(f"Python version: {python_version}")

    # Create test directories if they don't exist
    create_test_directories()

    # Determine test command
    cmd_parts = ["pytest"]

    # Add verbosity
    if args.verbose:
        cmd_parts.append("-v")
    else:
        cmd_parts.append("-v")  # Always show test names

    # Add asyncio configuration
    cmd_parts.append("--asyncio-mode=auto")

    # Add test selection
    if args.unit:
        cmd_parts.append("-m unit")
    elif args.integration:
        cmd_parts.append("-m integration")
    elif args.e2e:
        cmd_parts.append("-m e2e")
    elif args.file:
        cmd_parts.append(args.file)
    elif args.pattern:
        cmd_parts.append(f"-k {args.pattern}")

    # Add coverage
    if args.coverage or args.html:
        cmd_parts.append("--cov=service")
        cmd_parts.append("--cov-report=term-missing")

        if args.html:
            cmd_parts.append("--cov-report=html")

    # Add test output formatting
    cmd_parts.append("--tb=short")

    # Combine command
    cmd = " ".join(cmd_parts)

    # Run tests
    print_header(f"Running tests: {cmd}")
    result = run_command(cmd, capture_output=False)

    if result and result.returncode == 0:
        print_success("\nAll tests passed!")
        return 0
    else:
        print_error("\nSome tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())