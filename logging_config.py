"""
Logging Configuration for MindGraph Application

This module provides centralized logging configuration to avoid conflicts
with application-wide logging settings.
"""

import os
import logging
from dotenv import load_dotenv

load_dotenv()

def setup_agent_logging():
    """
    Setup logging configuration for agent modules.
    
    Returns:
        logger: Configured logger instance for agents
    """
    # Ensure logs directory exists
    os.makedirs("logs", exist_ok=True)
    
    # Create agent-specific logger
    agent_logger = logging.getLogger('mindgraph.agents')
    
    # Only configure if not already configured
    if not agent_logger.handlers:
        # Get log level from environment variable, default to INFO
        log_level_str = os.getenv('LOG_LEVEL', 'INFO').upper()
        log_level = getattr(logging, log_level_str, logging.INFO)
        agent_logger.setLevel(log_level)
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        agent_logger.addHandler(console_handler)
        
        # File handler
        log_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 
            "logs", 
            "agent.log"
        )
        file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        agent_logger.addHandler(file_handler)
        
        # Prevent propagation to avoid duplicate logs
        agent_logger.propagate = False
    
    return agent_logger
