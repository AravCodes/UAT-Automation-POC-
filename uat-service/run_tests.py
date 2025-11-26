#!/usr/bin/env python3
"""
Test runner script for UAT automation service.

This script provides a convenient way to run different test suites
with appropriate configurations.

Usage:
    python run_tests.py [test_type] [options]

Test Types:
    unit        - Run unit tests only (fast)
    integration - Run integration tests
    e2e         - Run end-to-end tests (requires sample app)
    smoke       - Run smoke tests for quick validation
    all         - Run all tests
    
Options:
    --verbose   - Verbose output
    --coverage  - Generate coverage report
    --parallel  - Run tests in parallel (requires pytest-xdist)
    --html      - Generate HTML report (requires pytest-html)
"""

import sys
import subprocess
import argparse
from pathlib import Path


def run_command(cmd: list[str], description: str) -> int:
    """Run a command and return exit code."""
    print(f"\n{'='*80}")
    print(f"{description}")
    print(f"{'='*80}\n")
    print(f"Command: {' '.join(cmd)}\n")
    
    result = subprocess.run(cmd)
    return result.returncode


def main():
    parser = argparse.ArgumentParser(description="Run UAT automation service tests")
    parser.add_argument(
        "test_type",
        choices=["unit", "integration", "e2e", "smoke", "all"],
        default="all",
        nargs="?",
        help="Type of tests to run"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Generate coverage report"
    )
    parser.add_argument(
        "--parallel", "-n",
        action="store_true",
        help="Run tests in parallel"
    )
    parser.add_argument(
        "--html",
        action="store_true",
        help="Generate HTML report"
    )
    parser.add_argument(
        "--markers", "-m",
        type=str,
        help="Run tests matching given mark expression"
    )
    
    args = parser.parse_args()
    
    # Build pytest command
    cmd = ["pytest"]
    
    # Add test path based on test type
    if args.test_type == "unit":
        cmd.extend(["-m", "unit", "tests/"])
        description = "Running Unit Tests"
    elif args.test_type == "integration":
        cmd.extend(["-m", "integration", "tests/integration/"])
        description = "Running Integration Tests"
    elif args.test_type == "e2e":
        cmd.extend(["-m", "e2e", "tests/e2e/"])
        description = "Running End-to-End Tests"
    elif args.test_type == "smoke":
        cmd.extend(["-m", "smoke", "tests/"])
        description = "Running Smoke Tests"
    else:  # all
        cmd.append("tests/")
        description = "Running All Tests"
    
    # Add custom markers if specified
    if args.markers:
        cmd.extend(["-m", args.markers])
    
    # Add verbose flag
    if args.verbose:
        cmd.append("-vv")
    else:
        cmd.append("-v")
    
    # Add coverage
    if args.coverage:
        cmd.extend([
            "--cov=app",
            "--cov-report=html",
            "--cov-report=term-missing"
        ])
    
    # Add parallel execution
    if args.parallel:
        cmd.extend(["-n", "auto"])
    
    # Add HTML report
    if args.html:
        cmd.extend([
            "--html=test-report.html",
            "--self-contained-html"
        ])
    
    # Run tests
    exit_code = run_command(cmd, description)
    
    # Print summary
    print(f"\n{'='*80}")
    if exit_code == 0:
        print("✓ All tests passed!")
    else:
        print(f"✗ Tests failed with exit code {exit_code}")
    print(f"{'='*80}\n")
    
    # Print coverage report location if generated
    if args.coverage:
        coverage_dir = Path("htmlcov")
        if coverage_dir.exists():
            print(f"Coverage report: {coverage_dir / 'index.html'}")
    
    # Print HTML report location if generated
    if args.html:
        report_file = Path("test-report.html")
        if report_file.exists():
            print(f"HTML report: {report_file}")
    
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
