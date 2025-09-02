"""
Test runner utilities and helpers.
"""
import pytest
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def run_all_tests():
    """Run all tests with coverage reporting."""
    pytest.main([
        '-v',
        '--cov=new_relic_exporter',
        '--cov=new_relic_metrics_exporter',
        '--cov=shared',
        '--cov-report=html',
        '--cov-report=term-missing',
        'tests/'
    ])


def run_integration_tests():
    """Run only integration tests."""
    pytest.main([
        '-v',
        '-m', 'integration',
        'tests/'
    ])


def run_unit_tests():
    """Run only unit tests."""
    pytest.main([
        '-v',
        '-m', 'not integration',
        'tests/'
    ])


if __name__ == "__main__":
    run_all_tests()