"""
Analytics and trend analysis service.

This module provides historical trend analysis, regression detection,
and coverage metrics for test runs. It supports filtering by module,
priority, status, and time range.
"""

from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass
from collections import defaultdict

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.models.story import ParsedStory, Priority
from app.services.storage.database import (
    TestRunModel,
    ScenarioResultModel,
    get_db_session
)
from app.core.logging import get_logger


logger = get_logger(__name__)


@dataclass
class TrendDataPoint:
    """Single data point in a trend analysis."""
    timestamp: datetime
    run_id: str
    total_scenarios: int
    passed_scenarios: int
    failed_scenarios: int
    pass_rate: float
    duration_ms: int
    flaky_count: int


@dataclass
class TrendAnalysis:
    """Complete trend analysis over time."""
    story_id: str
    time_range_start: datetime
    time_range_end: datetime
    total_runs: int
    data_points: list[TrendDataPoint]
    average_pass_rate: float
    pass_rate_trend: str  # "improving", "declining", "stable"
    average_duration_ms: int
    duration_trend: str  # "faster", "slower", "stable"
    total_flaky_tests: int


@dataclass
class FlakyTest:
    """Information about a flaky test scenario."""
    scenario_id: str
    occurrences: int
    last_seen: datetime
    pass_rate: float
    affected_runs: list[str]


@dataclass
class Regression:
    """Detected regression in test results."""
    scenario_id: str
    detected_at: datetime
    run_id: str
    previous_status: str
    current_status: str
    error_message: Optional[str]
    affected_criterion: Optional[str]


@dataclass
class CoverageMetrics:
    """Test coverage metrics for a story."""
    story_id: str
    total_criteria: int
    covered_criteria: int
    coverage_percentage: float
    total_scenarios: int
    scenarios_by_type: dict[str, int]
    scenarios_by_priority: dict[str, int]
    untested_criteria: list[str]


@dataclass
class FilterOptions:
    """Options for filtering analytics queries."""
    story_id: Optional[str] = None
    module: Optional[str] = None
    priority: Optional[Priority] = None
    status: Optional[str] = None
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
    limit: Optional[int] = None


class AnalyticsService:
    """
    Service for analyzing test results and generating insights.
    
    This service provides historical trend analysis, regression detection,
    flaky test identification, and coverage metrics calculation.
    """
    
    def __init__(self, db_session: Optional[Session] = None):
        """
        Initialize analytics service.
        
        Args:
            db_session: Database session (optional, will create if not provided)
        """
        self.db_session = db_session
        self._owns_session = db_session is None
    
    def __enter__(self):
        """Context manager entry."""
        if self._owns_session:
            self.db_session = next(get_db_session())
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if self._owns_session and self.db_session:
            self.db_session.close()
    
    def calculate_trends(
        self,
        story_id: str,
        days: int = 30,
        filters: Optional[FilterOptions] = None
    ) -> TrendAnalysis:
        """
        Analyze pass/fail trends over time.
        
        Args:
            story_id: Story ID to analyze
            days: Number of days to look back
            filters: Additional filter options
            
        Returns:
            TrendAnalysis: Trend analysis results
        """
        logger.info(
            "calculating_trends",
            extra={"story_id": story_id, "days": days}
        )
        
        # Calculate time range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Query test runs
        query = self.db_session.query(TestRunModel).filter(
            and_(
                TestRunModel.story_id == story_id,
                TestRunModel.started_at >= start_date,
                TestRunModel.started_at <= end_date,
                TestRunModel.status.in_(["passed", "failed", "partial"])
            )
        ).order_by(TestRunModel.started_at.asc())
        
        # Apply additional filters
        if filters:
            if filters.status:
                query = query.filter(TestRunModel.status == filters.status)
            if filters.from_date:
                query = query.filter(TestRunModel.started_at >= filters.from_date)
            if filters.to_date:
                query = query.filter(TestRunModel.started_at <= filters.to_date)
            if filters.limit:
                query = query.limit(filters.limit)
        
        runs = query.all()
        
        # Build data points
        data_points = []
        total_pass_rate = 0
        total_duration = 0
        total_flaky = 0
        
        for run in runs:
            pass_rate = (
                (run.passed_scenarios / run.total_scenarios * 100)
                if run.total_scenarios > 0 else 0
            )
            
            # Count flaky scenarios
            flaky_count = self.db_session.query(ScenarioResultModel).filter(
                and_(
                    ScenarioResultModel.run_id == run.id,
                    ScenarioResultModel.is_flaky == True
                )
            ).count()
            
            data_point = TrendDataPoint(
                timestamp=run.started_at,
                run_id=run.id,
                total_scenarios=run.total_scenarios,
                passed_scenarios=run.passed_scenarios,
                failed_scenarios=run.failed_scenarios,
                pass_rate=pass_rate,
                duration_ms=run.duration_ms or 0,
                flaky_count=flaky_count
            )
            data_points.append(data_point)
            
            total_pass_rate += pass_rate
            total_duration += (run.duration_ms or 0)
            total_flaky += flaky_count
        
        # Calculate averages
        num_runs = len(data_points)
        avg_pass_rate = total_pass_rate / num_runs if num_runs > 0 else 0
        avg_duration = total_duration // num_runs if num_runs > 0 else 0
        
        # Determine trends
        pass_rate_trend = self._calculate_trend(
            [dp.pass_rate for dp in data_points]
        )
        duration_trend = self._calculate_duration_trend(
            [dp.duration_ms for dp in data_points]
        )
        
        return TrendAnalysis(
            story_id=story_id,
            time_range_start=start_date,
            time_range_end=end_date,
            total_runs=num_runs,
            data_points=data_points,
            average_pass_rate=avg_pass_rate,
            pass_rate_trend=pass_rate_trend,
            average_duration_ms=avg_duration,
            duration_trend=duration_trend,
            total_flaky_tests=total_flaky
        )
    
    def detect_flaky_tests(
        self,
        story_id: Optional[str] = None,
        days: int = 30,
        min_occurrences: int = 2
    ) -> list[FlakyTest]:
        """
        Identify tests with inconsistent results.
        
        Args:
            story_id: Story ID to analyze (optional, analyzes all if not provided)
            days: Number of days to look back
            min_occurrences: Minimum number of flaky occurrences to report
            
        Returns:
            list[FlakyTest]: List of identified flaky tests
        """
        logger.info(
            "detecting_flaky_tests",
            extra={"story_id": story_id, "days": days}
        )
        
        # Calculate time range
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Query flaky scenarios
        query = self.db_session.query(
            ScenarioResultModel.scenario_id,
            func.count(ScenarioResultModel.id).label('occurrences'),
            func.max(ScenarioResultModel.completed_at).label('last_seen')
        ).join(
            TestRunModel,
            ScenarioResultModel.run_id == TestRunModel.id
        ).filter(
            and_(
                ScenarioResultModel.is_flaky == True,
                TestRunModel.started_at >= start_date
            )
        )
        
        if story_id:
            query = query.filter(TestRunModel.story_id == story_id)
        
        query = query.group_by(ScenarioResultModel.scenario_id).having(
            func.count(ScenarioResultModel.id) >= min_occurrences
        )
        
        results = query.all()
        
        # Build flaky test objects
        flaky_tests = []
        for scenario_id, occurrences, last_seen in results:
            # Get affected runs
            affected_runs_query = self.db_session.query(
                ScenarioResultModel.run_id
            ).filter(
                and_(
                    ScenarioResultModel.scenario_id == scenario_id,
                    ScenarioResultModel.is_flaky == True
                )
            ).distinct()
            
            affected_runs = [r[0] for r in affected_runs_query.all()]
            
            # Calculate pass rate for this scenario
            total_runs = self.db_session.query(
                func.count(ScenarioResultModel.id)
            ).filter(
                ScenarioResultModel.scenario_id == scenario_id
            ).scalar()
            
            passed_runs = self.db_session.query(
                func.count(ScenarioResultModel.id)
            ).filter(
                and_(
                    ScenarioResultModel.scenario_id == scenario_id,
                    ScenarioResultModel.status == "passed"
                )
            ).scalar()
            
            pass_rate = (passed_runs / total_runs * 100) if total_runs > 0 else 0
            
            flaky_tests.append(FlakyTest(
                scenario_id=scenario_id,
                occurrences=occurrences,
                last_seen=last_seen,
                pass_rate=pass_rate,
                affected_runs=affected_runs
            ))
        
        # Sort by occurrences (most flaky first)
        flaky_tests.sort(key=lambda x: x.occurrences, reverse=True)
        
        logger.info(
            "flaky_tests_detected",
            extra={"count": len(flaky_tests)}
        )
        
        return flaky_tests
    
    def detect_regressions(
        self,
        story_id: str,
        current_run_id: str,
        lookback_runs: int = 5
    ) -> list[Regression]:
        """
        Detect regressions by comparing current run with previous runs.
        
        Args:
            story_id: Story ID to analyze
            current_run_id: Current run ID to check for regressions
            lookback_runs: Number of previous runs to compare against
            
        Returns:
            list[Regression]: List of detected regressions
        """
        logger.info(
            "detecting_regressions",
            extra={"story_id": story_id, "run_id": current_run_id}
        )
        
        # Get current run
        current_run = self.db_session.query(TestRunModel).filter(
            TestRunModel.id == current_run_id
        ).first()
        
        if not current_run:
            logger.warning("current_run_not_found", extra={"run_id": current_run_id})
            return []
        
        # Get previous runs
        previous_runs = self.db_session.query(TestRunModel).filter(
            and_(
                TestRunModel.story_id == story_id,
                TestRunModel.started_at < current_run.started_at,
                TestRunModel.status.in_(["passed", "failed", "partial"])
            )
        ).order_by(TestRunModel.started_at.desc()).limit(lookback_runs).all()
        
        if not previous_runs:
            logger.info("no_previous_runs_found")
            return []
        
        # Get current run scenarios
        current_scenarios = self.db_session.query(ScenarioResultModel).filter(
            ScenarioResultModel.run_id == current_run_id
        ).all()
        
        regressions = []
        
        for current_scenario in current_scenarios:
            # Skip if current scenario passed
            if current_scenario.status == "passed":
                continue
            
            # Check if this scenario passed in previous runs
            for prev_run in previous_runs:
                prev_scenario = self.db_session.query(ScenarioResultModel).filter(
                    and_(
                        ScenarioResultModel.run_id == prev_run.id,
                        ScenarioResultModel.scenario_id == current_scenario.scenario_id
                    )
                ).first()
                
                if prev_scenario and prev_scenario.status == "passed":
                    # Regression detected!
                    regressions.append(Regression(
                        scenario_id=current_scenario.scenario_id,
                        detected_at=current_run.started_at,
                        run_id=current_run_id,
                        previous_status="passed",
                        current_status=current_scenario.status,
                        error_message=current_scenario.error_summary,
                        affected_criterion=None  # Would need scenario metadata
                    ))
                    break  # Only report once per scenario
        
        logger.info(
            "regressions_detected",
            extra={"count": len(regressions)}
        )
        
        return regressions
    
    def calculate_coverage(
        self,
        story: ParsedStory,
        scenarios: list
    ) -> CoverageMetrics:
        """
        Calculate test coverage metrics for a story.
        
        Args:
            story: Parsed user story
            scenarios: List of test scenarios
            
        Returns:
            CoverageMetrics: Coverage metrics
        """
        logger.info(
            "calculating_coverage",
            extra={"story_id": story.id}
        )
        
        total_criteria = len(story.acceptance_criteria)
        
        # Find which criteria have scenarios
        covered_criteria_ids = set()
        for scenario in scenarios:
            if hasattr(scenario, 'criterion_id'):
                covered_criteria_ids.add(scenario.criterion_id)
        
        covered_criteria = len(covered_criteria_ids)
        coverage_percentage = (
            (covered_criteria / total_criteria * 100)
            if total_criteria > 0 else 0
        )
        
        # Count scenarios by type
        scenarios_by_type = defaultdict(int)
        for scenario in scenarios:
            if hasattr(scenario, 'type'):
                scenarios_by_type[scenario.type.value] += 1
        
        # Count scenarios by priority
        scenarios_by_priority = defaultdict(int)
        for scenario in scenarios:
            if hasattr(scenario, 'priority'):
                scenarios_by_priority[scenario.priority.value] += 1
        
        # Find untested criteria
        untested_criteria = [
            criterion.id
            for criterion in story.acceptance_criteria
            if criterion.id not in covered_criteria_ids
        ]
        
        return CoverageMetrics(
            story_id=story.id,
            total_criteria=total_criteria,
            covered_criteria=covered_criteria,
            coverage_percentage=coverage_percentage,
            total_scenarios=len(scenarios),
            scenarios_by_type=dict(scenarios_by_type),
            scenarios_by_priority=dict(scenarios_by_priority),
            untested_criteria=untested_criteria
        )
    
    def get_filtered_runs(
        self,
        filters: FilterOptions
    ) -> list[TestRunModel]:
        """
        Get test runs with filtering support.
        
        Args:
            filters: Filter options
            
        Returns:
            list[TestRunModel]: Filtered test runs
        """
        query = self.db_session.query(TestRunModel)
        
        # Apply filters
        conditions = []
        
        if filters.story_id:
            conditions.append(TestRunModel.story_id == filters.story_id)
        
        if filters.status:
            conditions.append(TestRunModel.status == filters.status)
        
        if filters.from_date:
            conditions.append(TestRunModel.started_at >= filters.from_date)
        
        if filters.to_date:
            conditions.append(TestRunModel.started_at <= filters.to_date)
        
        if conditions:
            query = query.filter(and_(*conditions))
        
        # Order by most recent first
        query = query.order_by(TestRunModel.started_at.desc())
        
        # Apply limit
        if filters.limit:
            query = query.limit(filters.limit)
        
        return query.all()
    
    def get_summary_statistics(
        self,
        story_id: Optional[str] = None,
        days: int = 30
    ) -> dict:
        """
        Get summary statistics for test runs.
        
        Args:
            story_id: Story ID to analyze (optional)
            days: Number of days to look back
            
        Returns:
            dict: Summary statistics
        """
        start_date = datetime.utcnow() - timedelta(days=days)
        
        query = self.db_session.query(TestRunModel).filter(
            TestRunModel.started_at >= start_date
        )
        
        if story_id:
            query = query.filter(TestRunModel.story_id == story_id)
        
        runs = query.all()
        
        if not runs:
            return {
                "total_runs": 0,
                "total_scenarios": 0,
                "average_pass_rate": 0,
                "average_duration_ms": 0,
                "total_flaky_tests": 0
            }
        
        total_scenarios = sum(r.total_scenarios for r in runs)
        total_passed = sum(r.passed_scenarios for r in runs)
        total_duration = sum(r.duration_ms or 0 for r in runs)
        
        # Count flaky tests
        flaky_query = self.db_session.query(
            func.count(ScenarioResultModel.id)
        ).join(
            TestRunModel,
            ScenarioResultModel.run_id == TestRunModel.id
        ).filter(
            and_(
                ScenarioResultModel.is_flaky == True,
                TestRunModel.started_at >= start_date
            )
        )
        
        if story_id:
            flaky_query = flaky_query.filter(TestRunModel.story_id == story_id)
        
        total_flaky = flaky_query.scalar() or 0
        
        return {
            "total_runs": len(runs),
            "total_scenarios": total_scenarios,
            "average_pass_rate": (total_passed / total_scenarios * 100) if total_scenarios > 0 else 0,
            "average_duration_ms": total_duration // len(runs) if runs else 0,
            "total_flaky_tests": total_flaky
        }
    
    def _calculate_trend(self, values: list[float]) -> str:
        """
        Calculate trend direction from a list of values.
        
        Args:
            values: List of numeric values over time
            
        Returns:
            str: "improving", "declining", or "stable"
        """
        if len(values) < 2:
            return "stable"
        
        # Calculate simple linear regression slope
        n = len(values)
        x = list(range(n))
        x_mean = sum(x) / n
        y_mean = sum(values) / n
        
        numerator = sum((x[i] - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return "stable"
        
        slope = numerator / denominator
        
        # Determine trend based on slope
        if slope > 1:  # More than 1% improvement per run
            return "improving"
        elif slope < -1:  # More than 1% decline per run
            return "declining"
        else:
            return "stable"
    
    def _calculate_duration_trend(self, durations: list[int]) -> str:
        """
        Calculate duration trend from a list of durations.
        
        Args:
            durations: List of durations in milliseconds
            
        Returns:
            str: "faster", "slower", or "stable"
        """
        if len(durations) < 2:
            return "stable"
        
        # Calculate average of first half vs second half
        mid = len(durations) // 2
        first_half_avg = sum(durations[:mid]) / mid if mid > 0 else 0
        second_half_avg = sum(durations[mid:]) / (len(durations) - mid) if len(durations) > mid else 0
        
        if first_half_avg == 0:
            return "stable"
        
        change_percent = ((second_half_avg - first_half_avg) / first_half_avg) * 100
        
        if change_percent < -10:  # 10% faster
            return "faster"
        elif change_percent > 10:  # 10% slower
            return "slower"
        else:
            return "stable"
