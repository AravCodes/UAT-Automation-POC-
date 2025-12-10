"""
File storage manager for test artifacts.

This module provides file storage management for screenshots, logs, DOM snapshots,
and other test artifacts. Files are organized by run_id and scenario_id for easy
retrieval and cleanup.
"""

import os
import shutil
import json
from pathlib import Path
from typing import Optional, BinaryIO
from datetime import datetime, timedelta

from app.core.config import get_config
from app.core.exceptions import StorageException
from app.core.logging import get_logger


logger = get_logger(__name__)


class FileManager:
    """
    Manages file storage for test artifacts.
    
    Organizes files in a hierarchical structure:
    artifacts/
        runs/
            {run_id}/
                {scenario_id}/
                    screenshots/
                        step_{index}_{timestamp}.png
                    logs/
                        console_{timestamp}.log
                        network_{timestamp}.json
                    dom_snapshots/
                        step_{index}_{timestamp}.html
                metadata.json
    """
    
    def __init__(self, base_dir: Optional[str] = None):
        """
        Initialize file manager.
        
        Args:
            base_dir: Base directory for artifacts. If None, uses config value.
        """
        self.config = get_config()
        self.base_dir = Path(base_dir or self.config.artifacts_dir)
        self.runs_dir = self.base_dir / "runs"
        
        # Create base directories
        self._ensure_directory(self.base_dir)
        self._ensure_directory(self.runs_dir)
        
        logger.info(f"FileManager initialized with base_dir: {self.base_dir}")
    
    # ========================================================================
    # Directory Management
    # ========================================================================
    
    def _ensure_directory(self, path: Path) -> None:
        """
        Ensure directory exists, create if it doesn't.
        
        Args:
            path: Directory path to ensure exists
        """
        try:
            path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create directory {path}: {e}")
            raise StorageException(f"Failed to create directory: {e}")
    
    def get_run_dir(self, run_id: str) -> Path:
        """
        Get directory path for a test run.
        
        Args:
            run_id: Test run identifier
            
        Returns:
            Path: Directory path for the run
        """
        run_dir = self.runs_dir / run_id
        self._ensure_directory(run_dir)
        return run_dir
    
    def get_scenario_dir(self, run_id: str, scenario_id: str) -> Path:
        """
        Get directory path for a scenario within a run.
        
        Args:
            run_id: Test run identifier
            scenario_id: Scenario identifier
            
        Returns:
            Path: Directory path for the scenario
        """
        scenario_dir = self.get_run_dir(run_id) / scenario_id
        self._ensure_directory(scenario_dir)
        return scenario_dir
    
    def get_screenshots_dir(self, run_id: str, scenario_id: str) -> Path:
        """Get screenshots directory for a scenario."""
        screenshots_dir = self.get_scenario_dir(run_id, scenario_id) / "screenshots"
        self._ensure_directory(screenshots_dir)
        return screenshots_dir
    
    def get_logs_dir(self, run_id: str, scenario_id: str) -> Path:
        """Get logs directory for a scenario."""
        logs_dir = self.get_scenario_dir(run_id, scenario_id) / "logs"
        self._ensure_directory(logs_dir)
        return logs_dir
    
    def get_dom_snapshots_dir(self, run_id: str, scenario_id: str) -> Path:
        """Get DOM snapshots directory for a scenario."""
        dom_dir = self.get_scenario_dir(run_id, scenario_id) / "dom_snapshots"
        self._ensure_directory(dom_dir)
        return dom_dir
    
    # ========================================================================
    # Screenshot Management
    # ========================================================================
    
    def save_screenshot(
        self,
        run_id: str,
        scenario_id: str,
        step_index: int,
        screenshot_data: bytes,
        timestamp: Optional[datetime] = None
    ) -> str:
        """
        Save a screenshot for a test step.
        
        Args:
            run_id: Test run identifier
            scenario_id: Scenario identifier
            step_index: Index of the test step
            screenshot_data: Screenshot image data (PNG format)
            timestamp: Optional timestamp, defaults to current time
            
        Returns:
            str: Relative path to the saved screenshot
            
        Raises:
            StorageException: If save fails
        """
        try:
            screenshots_dir = self.get_screenshots_dir(run_id, scenario_id)
            
            if timestamp is None:
                timestamp = datetime.utcnow()
            
            timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S_%f")
            filename = f"step_{step_index}_{timestamp_str}.png"
            filepath = screenshots_dir / filename
            
            # Check file size
            size_mb = len(screenshot_data) / (1024 * 1024)
            if size_mb > self.config.max_artifact_size_mb:
                raise StorageException(
                    f"Screenshot size ({size_mb:.2f}MB) exceeds maximum "
                    f"allowed size ({self.config.max_artifact_size_mb}MB)"
                )
            
            # Write screenshot
            with open(filepath, "wb") as f:
                f.write(screenshot_data)
            
            # Return relative path from base_dir
            relative_path = filepath.relative_to(self.base_dir)
            
            logger.debug(
                f"Screenshot saved: {relative_path}",
                extra={
                    "run_id": run_id,
                    "scenario_id": scenario_id,
                    "step_index": step_index,
                    "size_mb": f"{size_mb:.2f}"
                }
            )
            
            return str(relative_path)
        
        except Exception as e:
            logger.error(f"Failed to save screenshot: {e}")
            raise StorageException(f"Failed to save screenshot: {e}")
    
    def get_screenshot(self, relative_path: str) -> bytes:
        """
        Retrieve a screenshot by its relative path.
        
        Args:
            relative_path: Relative path to the screenshot
            
        Returns:
            bytes: Screenshot image data
            
        Raises:
            StorageException: If file not found or read fails
        """
        try:
            filepath = self.base_dir / relative_path
            
            if not filepath.exists():
                raise StorageException(f"Screenshot not found: {relative_path}")
            
            with open(filepath, "rb") as f:
                return f.read()
        
        except Exception as e:
            logger.error(f"Failed to read screenshot: {e}")
            raise StorageException(f"Failed to read screenshot: {e}")
    
    # ========================================================================
    # Console Log Management
    # ========================================================================
    
    def save_console_logs(
        self,
        run_id: str,
        scenario_id: str,
        logs: list[str],
        timestamp: Optional[datetime] = None
    ) -> str:
        """
        Save console logs for a scenario.
        
        Args:
            run_id: Test run identifier
            scenario_id: Scenario identifier
            logs: List of console log messages
            timestamp: Optional timestamp, defaults to current time
            
        Returns:
            str: Relative path to the saved log file
            
        Raises:
            StorageException: If save fails
        """
        try:
            logs_dir = self.get_logs_dir(run_id, scenario_id)
            
            if timestamp is None:
                timestamp = datetime.utcnow()
            
            timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S_%f")
            filename = f"console_{timestamp_str}.log"
            filepath = logs_dir / filename
            
            # Write logs
            with open(filepath, "w", encoding="utf-8") as f:
                for log in logs:
                    f.write(f"{log}\n")
            
            # Return relative path
            relative_path = filepath.relative_to(self.base_dir)
            
            logger.debug(
                f"Console logs saved: {relative_path}",
                extra={
                    "run_id": run_id,
                    "scenario_id": scenario_id,
                    "log_count": len(logs)
                }
            )
            
            return str(relative_path)
        
        except Exception as e:
            logger.error(f"Failed to save console logs: {e}")
            raise StorageException(f"Failed to save console logs: {e}")
    
    # ========================================================================
    # Network Request Management
    # ========================================================================
    
    def save_network_requests(
        self,
        run_id: str,
        scenario_id: str,
        requests: list[dict],
        timestamp: Optional[datetime] = None
    ) -> str:
        """
        Save network requests for a scenario.
        
        Args:
            run_id: Test run identifier
            scenario_id: Scenario identifier
            requests: List of network request data
            timestamp: Optional timestamp, defaults to current time
            
        Returns:
            str: Relative path to the saved network log file
            
        Raises:
            StorageException: If save fails
        """
        try:
            logs_dir = self.get_logs_dir(run_id, scenario_id)
            
            if timestamp is None:
                timestamp = datetime.utcnow()
            
            timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S_%f")
            filename = f"network_{timestamp_str}.json"
            filepath = logs_dir / filename
            
            # Write network requests as JSON
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(requests, f, indent=2)
            
            # Return relative path
            relative_path = filepath.relative_to(self.base_dir)
            
            logger.debug(
                f"Network requests saved: {relative_path}",
                extra={
                    "run_id": run_id,
                    "scenario_id": scenario_id,
                    "request_count": len(requests)
                }
            )
            
            return str(relative_path)
        
        except Exception as e:
            logger.error(f"Failed to save network requests: {e}")
            raise StorageException(f"Failed to save network requests: {e}")
    
    # ========================================================================
    # DOM Snapshot Management
    # ========================================================================
    
    def save_dom_snapshot(
        self,
        run_id: str,
        scenario_id: str,
        step_index: int,
        dom_html: str,
        timestamp: Optional[datetime] = None
    ) -> str:
        """
        Save a DOM snapshot for a test step.
        
        Args:
            run_id: Test run identifier
            scenario_id: Scenario identifier
            step_index: Index of the test step
            dom_html: HTML content of the DOM
            timestamp: Optional timestamp, defaults to current time
            
        Returns:
            str: Relative path to the saved DOM snapshot
            
        Raises:
            StorageException: If save fails
        """
        try:
            dom_dir = self.get_dom_snapshots_dir(run_id, scenario_id)
            
            if timestamp is None:
                timestamp = datetime.utcnow()
            
            timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S_%f")
            filename = f"step_{step_index}_{timestamp_str}.html"
            filepath = dom_dir / filename
            
            # Check size
            size_mb = len(dom_html.encode('utf-8')) / (1024 * 1024)
            if size_mb > self.config.max_artifact_size_mb:
                raise StorageException(
                    f"DOM snapshot size ({size_mb:.2f}MB) exceeds maximum "
                    f"allowed size ({self.config.max_artifact_size_mb}MB)"
                )
            
            # Write DOM snapshot
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(dom_html)
            
            # Return relative path
            relative_path = filepath.relative_to(self.base_dir)
            
            logger.debug(
                f"DOM snapshot saved: {relative_path}",
                extra={
                    "run_id": run_id,
                    "scenario_id": scenario_id,
                    "step_index": step_index,
                    "size_mb": f"{size_mb:.2f}"
                }
            )
            
            return str(relative_path)
        
        except Exception as e:
            logger.error(f"Failed to save DOM snapshot: {e}")
            raise StorageException(f"Failed to save DOM snapshot: {e}")
    
    def get_dom_snapshot(self, relative_path: str) -> str:
        """
        Retrieve a DOM snapshot by its relative path.
        
        Args:
            relative_path: Relative path to the DOM snapshot
            
        Returns:
            str: HTML content of the DOM
            
        Raises:
            StorageException: If file not found or read fails
        """
        try:
            filepath = self.base_dir / relative_path
            
            if not filepath.exists():
                raise StorageException(f"DOM snapshot not found: {relative_path}")
            
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read()
        
        except Exception as e:
            logger.error(f"Failed to read DOM snapshot: {e}")
            raise StorageException(f"Failed to read DOM snapshot: {e}")
    
    # ========================================================================
    # Metadata Management
    # ========================================================================
    
    def save_run_metadata(
        self,
        run_id: str,
        metadata: dict
    ) -> str:
        """
        Save metadata for a test run.
        
        Args:
            run_id: Test run identifier
            metadata: Metadata dictionary
            
        Returns:
            str: Relative path to the metadata file
            
        Raises:
            StorageException: If save fails
        """
        try:
            run_dir = self.get_run_dir(run_id)
            filepath = run_dir / "metadata.json"
            
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2, default=str)
            
            relative_path = filepath.relative_to(self.base_dir)
            
            logger.debug(
                f"Run metadata saved: {relative_path}",
                extra={"run_id": run_id}
            )
            
            return str(relative_path)
        
        except Exception as e:
            logger.error(f"Failed to save run metadata: {e}")
            raise StorageException(f"Failed to save run metadata: {e}")
    
    def get_run_metadata(self, run_id: str) -> dict:
        """
        Retrieve metadata for a test run.
        
        Args:
            run_id: Test run identifier
            
        Returns:
            dict: Metadata dictionary
            
        Raises:
            StorageException: If file not found or read fails
        """
        try:
            run_dir = self.get_run_dir(run_id)
            filepath = run_dir / "metadata.json"
            
            if not filepath.exists():
                return {}
            
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        
        except Exception as e:
            logger.error(f"Failed to read run metadata: {e}")
            raise StorageException(f"Failed to read run metadata: {e}")
    
    # ========================================================================
    # Cleanup Operations
    # ========================================================================
    
    def delete_run_artifacts(self, run_id: str) -> None:
        """
        Delete all artifacts for a test run.
        
        Args:
            run_id: Test run identifier
            
        Raises:
            StorageException: If deletion fails
        """
        try:
            run_dir = self.get_run_dir(run_id)
            
            if run_dir.exists():
                shutil.rmtree(run_dir)
                logger.info(f"Deleted artifacts for run: {run_id}")
        
        except Exception as e:
            logger.error(f"Failed to delete run artifacts: {e}")
            raise StorageException(f"Failed to delete run artifacts: {e}")
    
    def cleanup_old_artifacts(self, days: Optional[int] = None) -> int:
        """
        Clean up artifacts older than specified days.
        
        Args:
            days: Number of days to retain. If None, uses config value.
            
        Returns:
            int: Number of runs cleaned up
            
        Raises:
            StorageException: If cleanup fails
        """
        try:
            retention_days = days or self.config.report_retention_days
            
            if retention_days == 0:
                logger.info("Artifact retention is set to forever, skipping cleanup")
                return 0
            
            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
            cleaned_count = 0
            
            for run_dir in self.runs_dir.iterdir():
                if not run_dir.is_dir():
                    continue
                
                # Check directory modification time
                mtime = datetime.fromtimestamp(run_dir.stat().st_mtime)
                
                if mtime < cutoff_date:
                    shutil.rmtree(run_dir)
                    cleaned_count += 1
                    logger.debug(f"Cleaned up old run: {run_dir.name}")
            
            logger.info(
                f"Cleaned up {cleaned_count} old runs (older than {retention_days} days)"
            )
            
            return cleaned_count
        
        except Exception as e:
            logger.error(f"Failed to cleanup old artifacts: {e}")
            raise StorageException(f"Failed to cleanup old artifacts: {e}")
    
    def get_storage_stats(self) -> dict:
        """
        Get storage statistics.
        
        Returns:
            dict: Storage statistics including total size, file counts, etc.
        """
        try:
            total_size = 0
            file_count = 0
            run_count = 0
            
            for run_dir in self.runs_dir.iterdir():
                if not run_dir.is_dir():
                    continue
                
                run_count += 1
                
                for filepath in run_dir.rglob("*"):
                    if filepath.is_file():
                        file_count += 1
                        total_size += filepath.stat().st_size
            
            return {
                "total_size_mb": total_size / (1024 * 1024),
                "total_size_gb": total_size / (1024 * 1024 * 1024),
                "file_count": file_count,
                "run_count": run_count,
                "base_dir": str(self.base_dir)
            }
        
        except Exception as e:
            logger.error(f"Failed to get storage stats: {e}")
            return {
                "error": str(e),
                "base_dir": str(self.base_dir)
            }


# ============================================================================
# Global File Manager Instance
# ============================================================================

_file_manager: Optional[FileManager] = None


def get_file_manager() -> FileManager:
    """
    Get the global file manager instance.
    
    Returns:
        FileManager: Global file manager
    """
    global _file_manager
    
    if _file_manager is None:
        _file_manager = FileManager()
    
    return _file_manager
