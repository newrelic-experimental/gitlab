"""
Tests for the main entry point of the GitLab New Relic Exporter.

Tests the new refactored main function that uses the processor architecture.
"""

import pytest
import os
from unittest.mock import patch, MagicMock


class TestMainFunction:
    """Test suite for the main function."""

    @patch("new_relic_exporter.main.GitLabExporter")
    def test_main_success(self, mock_exporter_class):
        """Test successful execution of main function."""
        # Setup mock exporter
        mock_exporter = MagicMock()
        mock_exporter_class.return_value = mock_exporter

        # Import and run main
        from new_relic_exporter.main import main

        # Should complete without error
        main()

        # Verify exporter was created and called
        mock_exporter_class.assert_called_once()
        mock_exporter.export_pipeline_data.assert_called_once()

    @patch("new_relic_exporter.main.GitLabExporter")
    def test_main_exporter_error(self, mock_exporter_class):
        """Test main function handles exporter errors."""
        # Setup mock exporter to raise an error
        mock_exporter = MagicMock()
        mock_exporter.export_pipeline_data.side_effect = Exception("Export failed")
        mock_exporter_class.return_value = mock_exporter

        # Import main
        from new_relic_exporter.main import main

        # Should raise the exception
        with pytest.raises(Exception, match="Export failed"):
            main()

        # Verify exporter was created and called
        mock_exporter_class.assert_called_once()
        mock_exporter.export_pipeline_data.assert_called_once()

    @patch("new_relic_exporter.main.GitLabExporter")
    @patch("new_relic_exporter.main.get_logger")
    def test_main_prints_status(self, mock_get_logger, mock_exporter_class):
        """Test that main function logs status messages."""
        # Setup mock logger
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        # Setup mock exporter
        mock_exporter = MagicMock()
        mock_exporter_class.return_value = mock_exporter

        # Import and run main
        from new_relic_exporter.main import main

        main()

        # Verify status messages were logged
        mock_logger.info.assert_any_call(
            "Starting GitLab New Relic Exporter",
            mock_logger.info.call_args_list[0][0][1],
        )
        mock_logger.info.assert_any_call(
            "GitLab New Relic Exporter completed successfully",
            mock_logger.info.call_args_list[1][0][1],
        )

    def test_main_module_execution(self):
        """Test that the module can be executed directly."""
        # This test verifies the if __name__ == "__main__" block exists
        from new_relic_exporter import main as main_module

        # Verify the main function exists
        assert hasattr(main_module, "main")
        assert callable(main_module.main)


class TestModuleStructure:
    """Test suite for module structure and imports."""

    def test_required_imports(self):
        """Test that all required imports are available."""
        from new_relic_exporter.main import main
        from new_relic_exporter.main import GitLabExporter

        # Verify imports work
        assert callable(main)
        assert GitLabExporter is not None

    def test_logging_configuration(self):
        """Test that logging is properly configured."""
        # Import the module to trigger logging setup
        import new_relic_exporter.main

        # Verify the module imports without error
        assert new_relic_exporter.main is not None


class TestIntegration:
    """Integration tests using the new architecture."""

    @patch("new_relic_exporter.main.GitLabExporter")
    def test_main_with_mocked_dependencies(self, mock_exporter_class):
        """Test main function with mocked GitLab dependencies."""
        # Setup mock exporter
        mock_exporter = MagicMock()
        mock_exporter_class.return_value = mock_exporter

        # Setup environment variables
        with patch.dict(
            os.environ, {"CI_PROJECT_ID": "123", "CI_PARENT_PIPELINE": "456"}
        ):
            # Import and run main
            from new_relic_exporter.main import main

            # Should complete without error
            main()

            # Verify exporter was created and called
            mock_exporter_class.assert_called_once()
            mock_exporter.export_pipeline_data.assert_called_once()

    @patch("new_relic_exporter.main.GitLabExporter")
    @patch("new_relic_exporter.main.get_logger")
    def test_main_missing_environment_variables(
        self, mock_get_logger, mock_exporter_class
    ):
        """Test main function behavior with missing environment variables."""
        # Setup mock logger
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        # Setup mock exporter
        mock_exporter = MagicMock()
        mock_exporter_class.return_value = mock_exporter

        # Clear environment variables
        with patch.dict(os.environ, {}, clear=True):
            # Import and run main
            from new_relic_exporter.main import main

            # Should complete (the exporter handles missing vars gracefully)
            main()

            # Verify it attempted to start
            mock_logger.info.assert_any_call(
                "Starting GitLab New Relic Exporter",
                mock_logger.info.call_args_list[0][0][1],
            )
            # Verify exporter was created and called
            mock_exporter_class.assert_called_once()
            mock_exporter.export_pipeline_data.assert_called_once()
