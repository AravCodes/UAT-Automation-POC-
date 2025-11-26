"""
Reporting and analytics services.

This package provides comprehensive reporting capabilities including:
- Multi-format report generation (HTML, JSON, PDF)
- Historical trend analysis
- Regression detection
- Flaky test identification
- Coverage metrics calculation
"""

from .report_generator import (
    ReportGenerator,
    Report,
    ReportFormat,
    ExecutiveSummary,
    StoryResultMapping
)
from .analytics import (
    AnalyticsService,
    TrendAnalysis,
    TrendDataPoint,
    FlakyTest,
    Regression,
    CoverageMetrics,
    FilterOptions
)

__all__ = [
    # Report Generator
    "ReportGenerator",
    "Report",
    "ReportFormat",
    "ExecutiveSummary",
    "StoryResultMapping",
    # Analytics
    "AnalyticsService",
    "TrendAnalysis",
    "TrendDataPoint",
    "FlakyTest",
    "Regression",
    "CoverageMetrics",
    "FilterOptions",
]
