from __future__ import annotations

import io
import logging

from app.core.logging import LoggerFactory, get_logger


def test_logger_creation():
    logger = LoggerFactory.create_logger("test_logger", level="DEBUG")
    assert logger.name == "test_logger"
    assert logger.level == logging.DEBUG


def test_logger_default_level():
    logger = LoggerFactory.create_logger("test_default")
    assert logger.level == logging.INFO


def test_logger_output():
    stream = io.StringIO()
    logger = LoggerFactory.create_logger(
        "test_output", level="INFO", stream=stream
    )
    logger.info("hello world")
    output = stream.getvalue()
    assert "hello world" in output
    assert "INFO" in output


def test_logger_reuses_handlers():
    logger = LoggerFactory.create_logger("test_reuse")
    handler_count = len(logger.handlers)
    same_logger = LoggerFactory.create_logger("test_reuse")
    assert len(same_logger.handlers) == handler_count


def test_logger_respects_level():
    stream = io.StringIO()
    logger = LoggerFactory.create_logger(
        "test_level", level="WARNING", stream=stream
    )
    logger.info("should not appear")
    logger.warning("should appear")
    output = stream.getvalue()
    assert "should not appear" not in output
    assert "should appear" in output


def test_get_logger_returns_logger():
    logger = get_logger("test_get")
    assert isinstance(logger, logging.Logger)
