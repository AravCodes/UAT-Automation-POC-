"""
Database models and setup using SQLAlchemy.

This module provides SQLAlchemy ORM models for persisting user stories,
acceptance criteria, test runs, and results. It supports both SQLite and
PostgreSQL databases with proper indexing for performance.
"""

from datetime import datetime
from typing import Optional, AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import (
    String, Integer, Float, Boolean, DateTime, Text, JSON,
    ForeignKey, Index, create_engine, event
)
from sqlalchemy.orm import (
    DeclarativeBase, Mapped, mapped_column, relationship,
    sessionmaker, Session
)
from sqlalchemy.ext.asyncio import (
    AsyncSession, create_async_engine, async_sessionmaker
)

from app.core.config import get_config


# ============================================================================
# Base Model
# ============================================================================

class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


# ============================================================================
# Story Models
# ============================================================================

class StoryModel(Base):
    """Database model for user stories."""
    
    __tablename__ = "stories"
    
    # Primary key
    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    
    # Story fields
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    role: Mapped[str] = mapped_column(String(255), nullable=False)
    feature: Mapped[str] = mapped_column(Text, nullable=False)
    benefit: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Parsing metadata
    parsing_method: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Method used: llm_primary, llm_fallback, nlp_legacy"
    )
    
    # JSON fields for complex data
    implicit_requirements: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="List of implicit requirements"
    )
    ambiguities: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="List of identified ambiguities"
    )
    metadata_json: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Additional metadata"
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    
    # Relationships
    acceptance_criteria: Mapped[list["AcceptanceCriterionModel"]] = relationship(
        back_populates="story",
        cascade="all, delete-orphan"
    )
    test_runs: Mapped[list["TestRunModel"]] = relationship(
        back_populates="story",
        cascade="all, delete-orphan"
    )
    
    # Indexes
    __table_args__ = (
        Index("idx_stories_created_at", "created_at"),
        Index("idx_stories_parsing_method", "parsing_method"),
    )
    
    def __repr__(self) -> str:
        return f"<StoryModel(id={self.id}, title={self.title})>"


class AcceptanceCriterionModel(Base):
    """Database model for acceptance criteria."""
    
    __tablename__ = "acceptance_criteria"
    
    # Primary key
    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    
    # Foreign key
    story_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("stories.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Criterion fields
    text: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Priority: critical, high, medium, low"
    )
    
    # Dependencies as JSON array
    dependencies: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="List of dependent criterion IDs"
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow
    )
    
    # Relationships
    story: Mapped["StoryModel"] = relationship(back_populates="acceptance_criteria")
    
    # Indexes
    __table_args__ = (
        Index("idx_criteria_story_id", "story_id"),
        Index("idx_criteria_priority", "priority"),
    )
    
    def __repr__(self) -> str:
        return f"<AcceptanceCriterionModel(id={self.id}, story_id={self.story_id})>"


# ============================================================================
# Test Run Models
# ============================================================================

class TestRunModel(Base):
    """Database model for test runs."""
    
    __tablename__ = "test_runs"
    
    # Primary key
    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    
    # Foreign key
    story_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("stories.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Run status
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Status: passed, failed, partial, running, error"
    )
    
    # Timestamps
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True
    )
    
    # Summary statistics
    total_scenarios: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    passed_scenarios: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_scenarios: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_scenarios: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    
    total_steps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    passed_steps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_steps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    
    # Duration in milliseconds
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # JSON fields for complex data
    environment: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Environment info (browser, OS, etc.)"
    )
    configuration: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Test configuration"
    )
    diagnostics: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Diagnostic information"
    )
    
    # Relationships
    story: Mapped["StoryModel"] = relationship(back_populates="test_runs")
    scenario_results: Mapped[list["ScenarioResultModel"]] = relationship(
        back_populates="test_run",
        cascade="all, delete-orphan"
    )
    
    # Indexes
    __table_args__ = (
        Index("idx_runs_story_id", "story_id"),
        Index("idx_runs_status", "status"),
        Index("idx_runs_started_at", "started_at"),
        Index("idx_runs_story_status", "story_id", "status"),
    )
    
    def __repr__(self) -> str:
        return f"<TestRunModel(id={self.id}, story_id={self.story_id}, status={self.status})>"


# ============================================================================
# Scenario Result Models
# ============================================================================

class ScenarioResultModel(Base):
    """Database model for scenario execution results."""
    
    __tablename__ = "scenario_results"
    
    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign key
    run_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("test_runs.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Scenario identification
    scenario_id: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Status: passed, failed, partial, skipped, error"
    )
    
    # Execution metrics
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_flaky: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    
    # Error information
    error_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Timestamps
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    test_run: Mapped["TestRunModel"] = relationship(back_populates="scenario_results")
    step_results: Mapped[list["StepResultModel"]] = relationship(
        back_populates="scenario_result",
        cascade="all, delete-orphan"
    )
    
    # Indexes
    __table_args__ = (
        Index("idx_scenario_results_run_id", "run_id"),
        Index("idx_scenario_results_scenario_id", "scenario_id"),
        Index("idx_scenario_results_status", "status"),
        Index("idx_scenario_results_is_flaky", "is_flaky"),
    )
    
    def __repr__(self) -> str:
        return f"<ScenarioResultModel(id={self.id}, scenario_id={self.scenario_id}, status={self.status})>"


# ============================================================================
# Step Result Models
# ============================================================================

class StepResultModel(Base):
    """Database model for test step execution results."""
    
    __tablename__ = "step_results"
    
    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign key
    scenario_result_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("scenario_results.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Step information
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Action type: navigate, click, type, assert, wait, etc."
    )
    target: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expected_outcome: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Status: passed, failed, skipped, error"
    )
    
    # Execution metrics
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    
    # Diagnostic information
    screenshot_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    dom_snapshot_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Logs as JSON arrays
    console_logs: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Console logs captured during step"
    )
    network_requests: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Network requests made during step"
    )
    
    # Timestamps
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    scenario_result: Mapped["ScenarioResultModel"] = relationship(
        back_populates="step_results"
    )
    
    # Indexes
    __table_args__ = (
        Index("idx_step_results_scenario_result_id", "scenario_result_id"),
        Index("idx_step_results_status", "status"),
        Index("idx_step_results_action", "action"),
    )
    
    def __repr__(self) -> str:
        return f"<StepResultModel(id={self.id}, step_index={self.step_index}, action={self.action})>"


# ============================================================================
# Database Engine and Session Management
# ============================================================================

class DatabaseManager:
    """Manages database connections and sessions."""
    
    def __init__(self):
        """Initialize database manager with configuration."""
        self.config = get_config()
        self.engine = None
        self.session_factory = None
        self._initialized = False
    
    def initialize(self) -> None:
        """
        Initialize database engine and create tables.
        
        This method sets up the database connection and creates all tables
        if they don't exist. It also configures SQLite-specific settings
        for better performance.
        """
        if self._initialized:
            return
        
        database_url = self.config.database_url
        
        # Create engine based on database type
        if database_url.startswith("sqlite"):
            # SQLite-specific configuration
            self.engine = create_engine(
                database_url,
                echo=self.config.database_echo,
                connect_args={"check_same_thread": False}
            )
            
            # Enable foreign key constraints for SQLite
            @event.listens_for(self.engine, "connect")
            def set_sqlite_pragma(dbapi_conn, connection_record):
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging
                cursor.close()
        
        else:
            # PostgreSQL or other databases
            self.engine = create_engine(
                database_url,
                echo=self.config.database_echo,
                pool_size=self.config.database_pool_size,
                max_overflow=self.config.database_max_overflow
            )
        
        # Create session factory
        self.session_factory = sessionmaker(
            bind=self.engine,
            autocommit=False,
            autoflush=False
        )
        
        # Create all tables
        Base.metadata.create_all(self.engine)
        
        self._initialized = True
    
    def get_session(self) -> Session:
        """
        Get a new database session.
        
        Returns:
            Session: SQLAlchemy session
            
        Raises:
            RuntimeError: If database is not initialized
        """
        if not self._initialized:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        
        return self.session_factory()
    
    @asynccontextmanager
    async def session_scope(self) -> AsyncGenerator[Session, None]:
        """
        Provide a transactional scope for database operations.
        
        This context manager automatically commits on success and rolls back
        on exceptions.
        
        Yields:
            Session: Database session
            
        Example:
            async with db_manager.session_scope() as session:
                story = session.query(StoryModel).first()
        """
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def close(self) -> None:
        """Close database engine and cleanup resources."""
        if self.engine:
            self.engine.dispose()
            self._initialized = False


# ============================================================================
# Global Database Manager Instance
# ============================================================================

_db_manager: Optional[DatabaseManager] = None


def get_db_manager() -> DatabaseManager:
    """
    Get the global database manager instance.
    
    Returns:
        DatabaseManager: Global database manager
    """
    global _db_manager
    
    if _db_manager is None:
        _db_manager = DatabaseManager()
        _db_manager.initialize()
    
    return _db_manager


def get_db_session() -> Session:
    """
    Get a new database session.
    
    This is a convenience function for dependency injection in FastAPI.
    
    Returns:
        Session: Database session
        
    Example:
        @app.get("/stories")
        def get_stories(db: Session = Depends(get_db_session)):
            return db.query(StoryModel).all()
    """
    db_manager = get_db_manager()
    session = db_manager.get_session()
    try:
        yield session
    finally:
        session.close()


def reset_database() -> None:
    """
    Reset the database by dropping and recreating all tables.
    
    WARNING: This will delete all data! Use only for testing.
    """
    db_manager = get_db_manager()
    Base.metadata.drop_all(db_manager.engine)
    Base.metadata.create_all(db_manager.engine)
