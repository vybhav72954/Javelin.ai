"""
JAVELIN.AI - Pytest Configuration and Shared Fixtures
======================================================

This file is automatically loaded by pytest and provides shared fixtures
and configuration for all test modules.
"""

import sys
from pathlib import Path

import pytest

# ============================================================================
# PATH SETUP
# ============================================================================

PROJECT_ROOT = Path(__file__).parent.parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))


# ============================================================================
# PYTEST HOOKS
# ============================================================================

def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "pipeline: mark test as requiring pipeline run")
    config.addinivalue_line("markers", "unit: mark test as unit test")


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers automatically."""
    for item in items:
        # Add 'pipeline' marker to tests in TestPipelineExecution
        if "PipelineExecution" in item.nodeid:
            item.add_marker(pytest.mark.slow)
            item.add_marker(pytest.mark.pipeline)

        # Add 'unit' marker to utility tests
        if "Utility" in item.nodeid:
            item.add_marker(pytest.mark.unit)


# ============================================================================
# SHARED FIXTURES
# ============================================================================

@pytest.fixture(scope="session")
def project_paths():
    """Return commonly used project paths."""
    return {
        "root": PROJECT_ROOT,
        "src": SRC_DIR,
        "data": PROJECT_ROOT / "data",
        "outputs": PROJECT_ROOT / "outputs",
        "tests": PROJECT_ROOT / "tests",
    }
