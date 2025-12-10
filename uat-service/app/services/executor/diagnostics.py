"""
Comprehensive diagnostics capture for test execution.

This module provides utilities for capturing screenshots, console logs,
network requests, and other diagnostic information during test execution.
It also generates execution timelines with step durations.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field

from playwright.async_api import Page, Request, Response, ConsoleMessage

from app.core.config import get_config
from app.core.exceptions import FileStorageException
from app.core.logging import get_logger


logger = get_logger(__name__)


@dataclass
class NetworkCapture:
    """Captured network request/response information."""
    
    url: str
    method: str
    status_code: Optional[int] = None
    request_headers: dict = field(default_factory=dict)
    response_headers: dict = field(default_factory=dict)
    request_body: Optional[str] = None
    response_body: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    duration_ms: Optional[int] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "url": self.url,
            "method": self.method,
            "status_code": self.status_code,
            "request_headers": self.request_headers,
            "response_headers": self.response_headers,
            "request_body": self.request_body,
            "response_body": self.response_body,
            "timestamp": self.timestamp,
            "duration_ms": self.duration_ms
        }


@dataclass
class ConsoleCapture:
    """Captured console message."""
    
    type: str  # log, warn, error, info, debug
    text: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    location: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "type": self.type,
            "text": self.text,
            "timestamp": self.timestamp,
            "location": self.location
        }


@dataclass
class TimelineEvent:
    """Event in the execution timeline."""
    
    timestamp: str
    event_type: str
    description: str
    duration_ms: Optional[int] = None
    details: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "description": self.description,
            "duration_ms": self.duration_ms,
            "details": self.details
        }


class DiagnosticsCapture:
    """
    Captures comprehensive diagnostics during test execution.
    
    Handles screenshots, console logs, network requests, DOM snapshots,
    and execution timeline generation.
    """
    
    def __init__(
        self,
        run_id: str,
        scenario_id: str,
        artifacts_dir: Optional[str] = None
    ):
        """
        Initialize diagnostics capture.
        
        Args:
            run_id: Test run ID
            scenario_id: Scenario ID
            artifacts_dir: Directory for storing artifacts (None = use config)
        """
        self.config = get_config()
        self.run_id = run_id
        self.scenario_id = scenario_id
        
        # Setup artifacts directory
        if artifacts_dir is None:
            artifacts_dir = self.config.artifacts_dir
        
        self.artifacts_dir = Path(artifacts_dir) / run_id / scenario_id
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        
        # Storage for captured data
        self.console_logs: list[ConsoleCapture] = []
        self.network_requests: list[NetworkCapture] = []
        self.timeline_events: list[TimelineEvent] = []
        self.screenshots: dict[str, str] = {}  # key -> path
        
        # Network tracking
        self._request_start_times: dict[str, datetime] = {}
        
        logger.debug(
            "diagnostics_capture_initialized",
            extra={
                "run_id": run_id,
                "scenario_id": scenario_id,
                "artifacts_dir": str(self.artifacts_dir)
            }
        )
    
    def setup_page_listeners(self, page: Page) -> None:
        """
        Setup event listeners on a Playwright page.
        
        Args:
            page: Playwright page to attach listeners to
        """
        # Console message listener
        if self.config.capture_console_logs:
            page.on("console", self._on_console_message)
        
        # Network request listener
        if self.config.capture_network:
            page.on("request", self._on_request)
            page.on("response", self._on_response)
            page.on("requestfailed", self._on_request_failed)
        
        logger.debug(
            "page_listeners_setup",
            extra={
                "scenario_id": self.scenario_id,
                "capture_console": self.config.capture_console_logs,
                "capture_network": self.config.capture_network
            }
        )
    
    def _on_console_message(self, msg: ConsoleMessage) -> None:
        """Handle console message event."""
        try:
            console_capture = ConsoleCapture(
                type=msg.type,
                text=msg.text,
                location=msg.location.get("url") if msg.location else None
            )
            self.console_logs.append(console_capture)
            
            logger.debug(
                "console_message_captured",
                extra={
                    "scenario_id": self.scenario_id,
                    "type": msg.type,
                    "text": msg.text[:100]  # Truncate for logging
                }
            )
        except Exception as e:
            logger.warning(
                "console_capture_failed",
                extra={"error": str(e)}
            )
    
    def _on_request(self, request: Request) -> None:
        """Handle request event."""
        try:
            # Track request start time
            self._request_start_times[request.url] = datetime.now()
            
            logger.debug(
                "network_request_started",
                extra={
                    "scenario_id": self.scenario_id,
                    "method": request.method,
                    "url": request.url
                }
            )
        except Exception as e:
            logger.warning(
                "request_tracking_failed",
                extra={"error": str(e)}
            )
    
    def _on_response(self, response: Response) -> None:
        """Handle response event."""
        try:
            request = response.request
            
            # Calculate duration
            duration_ms = None
            if request.url in self._request_start_times:
                start_time = self._request_start_times.pop(request.url)
                duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            
            # Capture network data
            network_capture = NetworkCapture(
                url=request.url,
                method=request.method,
                status_code=response.status,
                request_headers=dict(request.headers),
                response_headers=dict(response.headers),
                duration_ms=duration_ms
            )
            
            # Try to capture request/response bodies (only for certain content types)
            try:
                content_type = response.headers.get("content-type", "")
                if "json" in content_type or "text" in content_type:
                    # Only capture small responses
                    if int(response.headers.get("content-length", "0")) < 10000:
                        # Note: body() is async, we can't await here
                        # This is a limitation - bodies won't be captured in event handlers
                        pass
            except:
                pass
            
            self.network_requests.append(network_capture)
            
            logger.debug(
                "network_response_captured",
                extra={
                    "scenario_id": self.scenario_id,
                    "method": request.method,
                    "url": request.url,
                    "status": response.status,
                    "duration_ms": duration_ms
                }
            )
        except Exception as e:
            logger.warning(
                "response_capture_failed",
                extra={"error": str(e)}
            )
    
    def _on_request_failed(self, request: Request) -> None:
        """Handle request failure event."""
        try:
            # Remove from tracking
            self._request_start_times.pop(request.url, None)
            
            # Capture failed request
            network_capture = NetworkCapture(
                url=request.url,
                method=request.method,
                status_code=0,  # Failed request
                request_headers=dict(request.headers)
            )
            
            self.network_requests.append(network_capture)
            
            logger.debug(
                "network_request_failed",
                extra={
                    "scenario_id": self.scenario_id,
                    "method": request.method,
                    "url": request.url
                }
            )
        except Exception as e:
            logger.warning(
                "request_failure_capture_failed",
                extra={"error": str(e)}
            )
    
    async def capture_screenshot(
        self,
        page: Page,
        name: str,
        full_page: bool = False
    ) -> Optional[str]:
        """
        Capture a screenshot of the page.
        
        Args:
            page: Playwright page
            name: Name for the screenshot (without extension)
            full_page: Capture full scrollable page
        
        Returns:
            Path to the screenshot file, or None if capture failed
        """
        try:
            screenshot_path = self.artifacts_dir / f"{name}.png"
            
            await page.screenshot(
                path=str(screenshot_path),
                full_page=full_page
            )
            
            self.screenshots[name] = str(screenshot_path)
            
            logger.info(
                "screenshot_captured",
                extra={
                    "scenario_id": self.scenario_id,
                    "name": name,
                    "path": str(screenshot_path),
                    "full_page": full_page
                }
            )
            
            return str(screenshot_path)
            
        except Exception as e:
            logger.error(
                "screenshot_capture_failed",
                extra={
                    "scenario_id": self.scenario_id,
                    "name": name,
                    "error": str(e)
                },
                exc_info=True
            )
            return None
    
    async def capture_dom_snapshot(
        self,
        page: Page,
        name: str
    ) -> Optional[str]:
        """
        Capture DOM snapshot (HTML content).
        
        Args:
            page: Playwright page
            name: Name for the snapshot (without extension)
        
        Returns:
            Path to the snapshot file, or None if capture failed
        """
        try:
            snapshot_path = self.artifacts_dir / f"{name}.html"
            
            content = await page.content()
            
            with open(snapshot_path, "w", encoding="utf-8") as f:
                f.write(content)
            
            logger.info(
                "dom_snapshot_captured",
                extra={
                    "scenario_id": self.scenario_id,
                    "name": name,
                    "path": str(snapshot_path)
                }
            )
            
            return str(snapshot_path)
            
        except Exception as e:
            logger.error(
                "dom_snapshot_capture_failed",
                extra={
                    "scenario_id": self.scenario_id,
                    "name": name,
                    "error": str(e)
                },
                exc_info=True
            )
            return None
    
    def add_timeline_event(
        self,
        event_type: str,
        description: str,
        duration_ms: Optional[int] = None,
        details: Optional[dict] = None
    ) -> None:
        """
        Add an event to the execution timeline.
        
        Args:
            event_type: Type of event (e.g., "step_start", "step_end", "navigation")
            description: Human-readable description
            duration_ms: Duration of the event (if applicable)
            details: Additional details about the event
        """
        event = TimelineEvent(
            timestamp=datetime.now().isoformat(),
            event_type=event_type,
            description=description,
            duration_ms=duration_ms,
            details=details or {}
        )
        
        self.timeline_events.append(event)
        
        logger.debug(
            "timeline_event_added",
            extra={
                "scenario_id": self.scenario_id,
                "event_type": event_type,
                "description": description
            }
        )
    
    async def save_diagnostics_report(self) -> str:
        """
        Save all captured diagnostics to a JSON report.
        
        Returns:
            Path to the diagnostics report file
        """
        try:
            report_path = self.artifacts_dir / "diagnostics.json"
            
            report = {
                "run_id": self.run_id,
                "scenario_id": self.scenario_id,
                "generated_at": datetime.now().isoformat(),
                "console_logs": [log.to_dict() for log in self.console_logs],
                "network_requests": [req.to_dict() for req in self.network_requests],
                "timeline": [event.to_dict() for event in self.timeline_events],
                "screenshots": self.screenshots,
                "summary": {
                    "total_console_logs": len(self.console_logs),
                    "total_network_requests": len(self.network_requests),
                    "total_timeline_events": len(self.timeline_events),
                    "total_screenshots": len(self.screenshots)
                }
            }
            
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2)
            
            logger.info(
                "diagnostics_report_saved",
                extra={
                    "scenario_id": self.scenario_id,
                    "path": str(report_path),
                    "console_logs": len(self.console_logs),
                    "network_requests": len(self.network_requests),
                    "timeline_events": len(self.timeline_events)
                }
            )
            
            return str(report_path)
            
        except Exception as e:
            logger.error(
                "diagnostics_report_save_failed",
                extra={
                    "scenario_id": self.scenario_id,
                    "error": str(e)
                },
                exc_info=True
            )
            raise FileStorageException(
                f"Failed to save diagnostics report: {str(e)}",
                file_path=str(report_path),
                operation="save_diagnostics",
                original_exception=e
            )
    
    def get_console_logs(self, log_type: Optional[str] = None) -> list[ConsoleCapture]:
        """
        Get captured console logs, optionally filtered by type.
        
        Args:
            log_type: Filter by log type (log, warn, error, etc.)
        
        Returns:
            List of console captures
        """
        if log_type:
            return [log for log in self.console_logs if log.type == log_type]
        return self.console_logs
    
    def get_network_requests(
        self,
        method: Optional[str] = None,
        status_code: Optional[int] = None
    ) -> list[NetworkCapture]:
        """
        Get captured network requests, optionally filtered.
        
        Args:
            method: Filter by HTTP method
            status_code: Filter by status code
        
        Returns:
            List of network captures
        """
        requests = self.network_requests
        
        if method:
            requests = [req for req in requests if req.method == method]
        
        if status_code is not None:
            requests = [req for req in requests if req.status_code == status_code]
        
        return requests
    
    def get_timeline_summary(self) -> dict:
        """
        Get a summary of the execution timeline.
        
        Returns:
            Dictionary with timeline statistics
        """
        if not self.timeline_events:
            return {
                "total_events": 0,
                "total_duration_ms": 0,
                "event_types": {}
            }
        
        # Count events by type
        event_types = {}
        for event in self.timeline_events:
            event_types[event.event_type] = event_types.get(event.event_type, 0) + 1
        
        # Calculate total duration
        total_duration = sum(
            event.duration_ms for event in self.timeline_events
            if event.duration_ms is not None
        )
        
        return {
            "total_events": len(self.timeline_events),
            "total_duration_ms": total_duration,
            "event_types": event_types,
            "first_event": self.timeline_events[0].timestamp,
            "last_event": self.timeline_events[-1].timestamp
        }


# ============================================================================
# Utility Functions
# ============================================================================

def create_diagnostics_capture(
    run_id: str,
    scenario_id: str,
    artifacts_dir: Optional[str] = None
) -> DiagnosticsCapture:
    """
    Create a diagnostics capture instance.
    
    Args:
        run_id: Test run ID
        scenario_id: Scenario ID
        artifacts_dir: Directory for artifacts
    
    Returns:
        DiagnosticsCapture instance
    """
    return DiagnosticsCapture(
        run_id=run_id,
        scenario_id=scenario_id,
        artifacts_dir=artifacts_dir
    )
