"""
Storage services for database, file management, and caching.

This package provides storage layer functionality including:
- SQLAlchemy database models and session management
- File storage for test artifacts (screenshots, logs, DOM snapshots)
- Redis caching for performance optimization
"""

from .database import (
    Base,
    StoryModel,
    AcceptanceCriterionModel,
    TestRunModel,
    ScenarioResultModel,
    StepResultModel,
    DatabaseManager,
    get_db_manager,
    get_db_session,
    reset_database
)

from .file_manager import (
    FileManager,
    get_file_manager
)

from .cache import (
    CacheManager,
    get_cache_manager,
    cached
)


__all__ = [
    # Database
    "Base",
    "StoryModel",
    "AcceptanceCriterionModel",
    "TestRunModel",
    "ScenarioResultModel",
    "StepResultModel",
    "DatabaseManager",
    "get_db_manager",
    "get_db_session",
    "reset_database",
    
    # File Manager
    "FileManager",
    "get_file_manager",
    
    # Cache
    "CacheManager",
    "get_cache_manager",
    "cached",
]
