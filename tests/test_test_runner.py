"""
Tests for test runner utilities.
"""

import pytest
from unittest.mock import patch, MagicMock
from tests.test_runner import run_all_tests, run_integration_tests, run_unit_tests


class TestTestRunner:
    """Test test runner functions."""

    @patch("tests.test_runner.pytest.main")
    def test_run_all_tests(self, mock_pytest_main):
        """Test run_all_tests function."""
        mock_pytest_main.return_value = 0

        result = run_all_tests()

        expected_args = [
            "-v",
            "--cov=new_relic_exporter",
            "--cov=new_relic_metrics_exporter",
            "--cov=shared",
            "--cov-report=html",
            "--cov-report=term-missing",
            "tests/",
        ]

        mock_pytest_main.assert_called_once_with(expected_args)
        assert result == 0

    @patch("tests.test_runner.pytest.main")
    def test_run_all_tests_failure(self, mock_pytest_main):
        """Test run_all_tests function when tests fail."""
        mock_pytest_main.return_value = 1

        result = run_all_tests()

        mock_pytest_main.assert_called_once()
        assert result == 1

    @patch("tests.test_runner.pytest.main")
    def test_run_integration_tests(self, mock_pytest_main):
        """Test run_integration_tests function."""
        mock_pytest_main.return_value = 0

        result = run_integration_tests()

        expected_args = ["-v", "-m", "integration", "tests/"]

        mock_pytest_main.assert_called_once_with(expected_args)
        assert result == 0

    @patch("tests.test_runner.pytest.main")
    def test_run_integration_tests_failure(self, mock_pytest_main):
        """Test run_integration_tests function when tests fail."""
        mock_pytest_main.return_value = 2

        result = run_integration_tests()

        mock_pytest_main.assert_called_once()
        assert result == 2

    @patch("tests.test_runner.pytest.main")
    def test_run_unit_tests(self, mock_pytest_main):
        """Test run_unit_tests function."""
        mock_pytest_main.return_value = 0

        result = run_unit_tests()

        expected_args = ["-v", "-m", "not integration", "tests/"]

        mock_pytest_main.assert_called_once_with(expected_args)
        assert result == 0

    @patch("tests.test_runner.pytest.main")
    def test_run_unit_tests_failure(self, mock_pytest_main):
        """Test run_unit_tests function when tests fail."""
        mock_pytest_main.return_value = 3

        result = run_unit_tests()

        mock_pytest_main.assert_called_once()
        assert result == 3

    @patch("tests.test_runner.pytest.main")
    def test_run_unit_tests_exception(self, mock_pytest_main):
        """Test run_unit_tests function when pytest raises exception."""
        mock_pytest_main.side_effect = Exception("Pytest failed to start")

        with pytest.raises(Exception, match="Pytest failed to start"):
            run_unit_tests()

        mock_pytest_main.assert_called_once()

    def test_all_functions_exist(self):
        """Test that all expected functions exist and are callable."""
        assert callable(run_all_tests)
        assert callable(run_integration_tests)
        assert callable(run_unit_tests)

    def test_function_docstrings(self):
        """Test that functions have proper docstrings."""
        assert run_all_tests.__doc__ == "Run all tests with coverage reporting."
        assert run_integration_tests.__doc__ == "Run only integration tests."
        assert run_unit_tests.__doc__ == "Run only unit tests."
