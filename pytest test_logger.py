import os
import tempfile
import json
from pathlib import Path
import logging
import pytest
from unittest.mock import patch, MagicMock

# Import our modules
from logging_config import LoggingConfig, get_logger
from audit_logger import AuditLogger, setup_audit_logging
from performance_logger import PerformanceLogger, setup_performance_logging


def test_logging_configuration():
    """Test basic logging configuration"""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Setup logging config to use temporary directory
        log_config = LoggingConfig(temp_dir)
        
        # Create logger
        logger = log_config.setup_logging(
            app_name="TestApp",
            log_level="DEBUG"
        )
        
        assert logger is not None
        assert logger.name == "TestApp"
        assert logger.level == logging.DEBUG


def test_console_logging():
    """Test console logging functionality"""
    with tempfile.TemporaryDirectory() as temp_dir:
        log_config = LoggingConfig(temp_dir)
        logger = log_config.setup_logging(app_name="ConsoleTest")
        
        # Test that we can log to console
        logger.info("This is a test message")


def test_file_logging():
    """Test file logging functionality"""
    with tempfile.TemporaryDirectory() as temp_dir:
        log_config = LoggingConfig(temp_dir)
        logger = log_config.setup_logging(app_name="FileTest")
        
        # Create some logs
        logger.info("File test info message")
        logger.error("File test error message")
        
        # Check that the log file was created and has content
        log_file = Path(temp_dir) / "logs" / "FileTest.log"
        assert log_file.exists()
        
        with open(log_file, 'r') as f:
            content = f.read()
            assert "File test info message" in content
            assert "File test error message" in content


def test_audit_logging():
    """Test audit logging functionality"""
    with tempfile.TemporaryDirectory() as temp_dir:
        log_config = LoggingConfig(temp_dir)
        logger = log_config.setup_logging(app_name="AuditTest")
        
        # Setup audit logging
        setup_audit_logging(logger)
        
        # Test audit event logging
        logger.audit(
            event_type="USER_LOGIN",
            user_id="user123",
            resource="login_page",
            action="attempt"
        )
        
        # Check that the audit log file was created and has content
        audit_file = Path(temp_dir) / "logs" / "AuditTest_audit.log"
        assert audit_file.exists()
        
        with open(audit_file, 'r') as f:
            content = f.read()
            assert "USER_LOGIN" in content
            assert "user123" in content


def test_performance_logging():
    """Test performance logging functionality"""
    with tempfile.TemporaryDirectory() as temp_dir:
        log_config = LoggingConfig(temp_dir)
        logger = log_config.setup_logging(app_name="PerfTest")
        
        # Setup performance logging
        setup_performance_logging(logger)
        
        # Test performance logging
        start_time = 0.1
        end_time = 0.2
        
        logger.performance(
            operation_name="test_operation",
            start_time=start_time,
            end_time=end_time
        )
        
        # Check that we can log function performance
        @logger.log_function_performance("sample_function")
        def sample_func():
            return "result"
            
        result = sample_func()
        assert result == "result"


def test_audit_context_manager():
    """Test audit context manager functionality"""
    with tempfile.TemporaryDirectory() as temp_dir:
        log_config = LoggingConfig(temp_dir)
        logger = log_config.setup_logging(app_name="AuditContextTest")
        
        # Setup audit logging
        setup_audit_logging(logger)
        
        # Test the context manager
        try:
            with logger.audit_context("TEST_OPERATION", "user123"):
                raise ValueError("Test exception")
        except ValueError:
            pass  # Expected


def test_logger_setup():
    """Test complete logger setup"""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Mock the logging config to use temporary directory
        original_config = LoggingConfig.__init__
        
        def mock_init(self, config_dir):
            self.config_dir = Path(temp_dir)
            self.log_dir = self.config_dir / "logs"
            self.log_dir.mkdir(exist_ok=True)
            
        LoggingConfig.__init__ = mock_init
        
        try:
            from logger_setup import get_production_logger
            
            # Test complete setup
            logger = get_production_logger("ProductionTest")
            
            assert logger is not None
            assert hasattr(logger, 'audit')
            assert hasattr(logger, 'performance')
            assert hasattr(logger, 'log_function_performance')
            
        finally:
            LoggingConfig.__init__ = original_config


def test_log_level_configuration():
    """Test different log levels"""
    with tempfile.TemporaryDirectory() as temp_dir:
        log_config = LoggingConfig(temp_dir)
        
        # Test INFO level
        logger = log_config.setup_logging(app_name="LevelTest", log_level="INFO")
        assert logger.level == logging.INFO
        
        # Test DEBUG level
        logger = log_config.setup_logging(app_name="LevelTest2", log_level="DEBUG")
        assert logger.level == logging.DEBUG


def test_rotating_logs():
    """Test that logs are properly rotated"""
    with tempfile.TemporaryDirectory() as temp_dir:
        log_config = LoggingConfig(temp_dir)
        
        # Create a logger with small max file size for testing
        logger = log_config.setup_logging(
            app_name="RotateTest",
            enable_console=False,
            max_log_size=10,  # Very small to force rotation quickly
            backup_count=2
        )
        
        # Generate enough content to trigger rotation
        for i in range(10):
            logger.info(f"Log message {i}")
            
        # Check that log files were created (at least one)
        log_dir = Path(temp_dir) / "logs"
        log_files = list(log_dir.glob("RotateTest.log*"))
        
        assert len(log_files) >= 1


def test_exception_logging():
    """Test exception logging"""
    with tempfile.TemporaryDirectory() as temp_dir:
        log_config = LoggingConfig(temp_dir)
        logger = log_config.setup_logging(app_name="ExceptionTest")
        
        try:
            raise ValueError("Test exception for logging")
        except Exception:
            logger.exception("This is an exception test")


def test_structured_logging():
    """Test structured logging in audit logs"""
    with tempfile.TemporaryDirectory() as temp_dir:
        log_config = LoggingConfig(temp_dir)
        logger = log_config.setup_logging(app_name="StructuredTest")
        
        setup_audit_logging(logger)
        
        # Log a structured event
        logger.audit(
            event_type="API_CALL",
            user_id="user456",
            resource="/api/users",
            action="GET",
            details={"status": 200, "duration_ms": 150},
            success=True
        )
        
        # Verify the JSON structure in audit log
        audit_file = Path(temp_dir) / "logs" / "StructuredTest_audit.log"
        assert audit_file.exists()
        
        with open(audit_file, 'r') as f:
            content = f.read()
            # Should contain valid JSON
            json_data = json.loads(content.split('\n')[0])
            assert json_data['event_type'] == "API_CALL"
            assert json_data['user_id'] == "user456"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
