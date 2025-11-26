#!/usr/bin/env python3
"""
Test validation script.

This script validates that the test suite is properly configured
and can be discovered by pytest.
"""

import sys
import subprocess
from pathlib import Path


def run_command(cmd: list[str]) -> tuple[int, str]:
    """Run a command and return exit code and output."""
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True
    )
    return result.returncode, result.stdout + result.stderr


def main():
    print("="*80)
    print("UAT Automation Service - Test Validation")
    print("="*80)
    print()
    
    # Check if pytest is installed
    print("1. Checking pytest installation...")
    exit_code, output = run_command(["pytest", "--version"])
    if exit_code != 0:
        print("   ✗ pytest not installed")
        print("   Install with: pip install pytest pytest-asyncio")
        return 1
    print(f"   ✓ {output.strip()}")
    print()
    
    # Check test discovery
    print("2. Discovering tests...")
    exit_code, output = run_command(["pytest", "--collect-only", "-q"])
    if exit_code != 0:
        print("   ✗ Test discovery failed")
        print(output)
        return 1
    
    # Count tests
    lines = output.strip().split("\n")
    test_count = 0
    for line in lines:
        if "test" in line.lower():
            test_count += 1
    
    print(f"   ✓ Discovered {test_count} tests")
    print()
    
    # Check test markers
    print("3. Checking test markers...")
    exit_code, output = run_command(["pytest", "--markers"])
    if exit_code != 0:
        print("   ✗ Failed to list markers")
        return 1
    
    markers = ["unit", "integration", "e2e", "smoke", "slow", "requires_groq", "requires_sample_app"]
    found_markers = []
    for marker in markers:
        if marker in output:
            found_markers.append(marker)
    
    print(f"   ✓ Found {len(found_markers)}/{len(markers)} markers")
    for marker in found_markers:
        print(f"     - {marker}")
    print()
    
    # Check test files
    print("4. Checking test files...")
    test_files = [
        "tests/test_groq_client.py",
        "tests/integration/test_complete_flow.py",
        "tests/e2e/test_sample_app.py",
        "tests/conftest.py"
    ]
    
    missing_files = []
    for test_file in test_files:
        if not Path(test_file).exists():
            missing_files.append(test_file)
    
    if missing_files:
        print(f"   ✗ Missing {len(missing_files)} test files:")
        for file in missing_files:
            print(f"     - {file}")
        return 1
    
    print(f"   ✓ All {len(test_files)} test files found")
    print()
    
    # Check fixtures
    print("5. Checking fixtures...")
    fixture_file = Path("fixtures/sample-stories.json")
    if not fixture_file.exists():
        print(f"   ⚠ Sample stories fixture not found: {fixture_file}")
        print("     E2E tests will be skipped")
    else:
        print(f"   ✓ Sample stories fixture found")
    print()
    
    # Check configuration
    print("6. Checking pytest configuration...")
    pytest_ini = Path("pytest.ini")
    if not pytest_ini.exists():
        print("   ⚠ pytest.ini not found")
    else:
        print("   ✓ pytest.ini found")
    print()
    
    # Summary
    print("="*80)
    print("Validation Summary")
    print("="*80)
    print()
    print("✓ Test suite is properly configured")
    print()
    print("Next steps:")
    print("  1. Run unit tests:        pytest -m unit")
    print("  2. Run integration tests: pytest -m integration")
    print("  3. Run smoke tests:       pytest -m smoke")
    print("  4. Run all tests:         pytest")
    print()
    print("For e2e tests:")
    print("  1. Start sample app:      cd ../sample-app && npm run dev")
    print("  2. Run e2e tests:         pytest -m e2e")
    print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
