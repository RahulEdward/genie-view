"""
Logging Configuration
Uses loguru for structured logging
"""

import sys
from loguru import logger


def setup_logger(log_level: str = "INFO"):
    """Configure loguru logger"""
    
    # Remove default handler
    logger.remove()
    
    # Add console handler with custom format
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=log_level,
        colorize=True
    )
    
    # Add file handler for errors
    logger.add(
        "logs/error.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="ERROR",
        rotation="10 MB",
        retention="7 days"
    )
    
    # Add file handler for all logs
    logger.add(
        "logs/app.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level=log_level,
        rotation="50 MB",
        retention="7 days"
    )
    
    return logger


# Export logger instance
__all__ = ["logger", "setup_logger"]
