"""
Test scenario generator from acceptance criteria.

This module generates comprehensive BDD test scenarios from acceptance
criteria, including positive, negative, and edge case scenarios with
dependency detection and priority assignment.
"""

import uuid
from typing import Optional
from collections import defaultdict

from app.models.story import AcceptanceCriterion, Priority
from app.models.test_scenario import (
    TestScenario,
    TestStep,
    ScenarioType,
    ActionType,
)
from app.services.llm.groq_client import GroqClient
from app.services.llm.prompt_templates import get_scenario_generation_prompt
from app.core.exceptions import (
    ScenarioGenerationException,
    LLMException,
)
from app.core.logging import get_logger


logger = get_logger(__name__)


class DependencyGraph:
    """
    Represents dependencies between test scenarios.
    
    This graph helps determine the execution order of scenarios
    when some scenarios depend on others being executed first.
    """
    
    def __init__(self):
        self.dependencies: dict[str, list[str]] = defaultdict(list)
        self.reverse_dependencies: dict[str, list[str]] = defaultdict(list)
    
    def add_dependency(self, scenario_id: str, depends_on: str):
        """
        Add a dependency relationship.
        
        Args:
            scenario_id: The scenario that has a dependency
            depends_on: The scenario that must be executed first
        """
        self.dependencies[scenario_id].append(depends_on)
        self.reverse_dependencies[depends_on].append(scenario_id)
    
    def get_dependencies(self, scenario_id: str) -> list[str]:
        """Get all scenarios that this scenario depends on."""
        return self.dependencies.get(scenario_id, [])
    
    def get_dependents(self, scenario_id: str) -> list[str]:
        """Get all scenarios that depend on this scenario."""
        return self.reverse_dependencies.get(scenario_id, [])
    
    def get_execution_order(self) -> list[str]:
        """
        Get a valid execution order respecting all dependencies.
        
        Uses topological sort to determine execution order.
        
        Returns:
            list[str]: Ordered list of scenario IDs
        """
        # Calculate in-degree for each node
        in_degree = defaultdict(int)
        all_scenarios = set(self.dependencies.keys()) | set(self.reverse_dependencies.keys())
        
        for scenario_id in all_scenarios:
            in_degree[scenario_id] = len(self.dependencies.get(scenario_id, []))
        
        # Find all nodes with no dependencies
        queue = [s for s in all_scenarios if in_degree[s] == 0]
        result = []
        
        while queue:
            # Sort queue for deterministic ordering
            queue.sort()
            current = queue.pop(0)
            result.append(current)
            
            # Reduce in-degree for dependent scenarios
            for dependent in self.reverse_dependencies.get(current, []):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)
        
        # Check for cycles
        if len(result) != len(all_scenarios):
            logger.warning(
                "dependency_cycle_detected",
                extra={
                    "resolved_count": len(result),
                    "total_count": len(all_scenarios),
                }
            )
        
        return result


class ScenarioGenerator:
    """
    Generate comprehensive test scenarios from acceptance criteria.
    
    This generator uses LLM to create positive, negative, and edge case
    scenarios with Given-When-Then format and executable test steps.
    It also detects dependencies and assigns priorities.
    
    Requirements: 2.2, 2.3, 2.4, 2.6, 2.7
    """
    
    def __init__(self, groq_client: Optional[GroqClient] = None):
        """
        Initialize the scenario generator.
        
        Args:
            groq_client: Optional GroqClient instance (creates new if None)
        """
        self.groq_client = groq_client
        self._owns_client = groq_client is None
        
        logger.info("scenario_generator_initialized")
    
    async def __aenter__(self):
        """Async context manager entry."""
        if self._owns_client:
            self.groq_client = GroqClient()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._owns_client and self.groq_client:
            await self.groq_client.close()
    
    async def generate_scenarios(
        self,
        criteria: list[AcceptanceCriterion],
    ) -> list[TestScenario]:
        """
        Generate comprehensive test scenarios from acceptance criteria.
        
        This method generates positive, negative, and edge case scenarios
        for each acceptance criterion using LLM. It also detects dependencies
        and assigns appropriate priorities.
        
        Args:
            criteria: List of acceptance criteria to generate scenarios for
        
        Returns:
            list[TestScenario]: Generated test scenarios
            
        Raises:
            ScenarioGenerationException: If scenario generation fails
        
        Requirements: 2.2, 2.3, 2.4, 2.6, 2.7
        """
        if not criteria:
            raise ScenarioGenerationException(
                "Cannot generate scenarios from empty criteria list"
            )
        
        logger.info(
            "scenario_generation_started",
            extra={
                "criteria_count": len(criteria),
            }
        )
        
        try:
            # Extract criteria texts for prompt
            criteria_texts = [c.text for c in criteria]
            
            # Get the prompt template
            prompt = get_scenario_generation_prompt(criteria_texts)
            
            # Call LLM to generate scenarios
            response = await self.groq_client.generate_scenarios(
                acceptance_criteria=criteria_texts,
                prompt_template=prompt,
            )
            
            # Parse response into TestScenario objects
            scenarios_data = response.get("scenarios", [])
            
            if not scenarios_data:
                raise ScenarioGenerationException(
                    "LLM returned no scenarios",
                    details={"response": response}
                )
            
            scenarios = []
            for scenario_data in scenarios_data:
                # Parse test steps
                test_steps = []
                for step_data in scenario_data.get("test_steps", []):
                    step = TestStep(
                        action=ActionType(step_data.get("action")),
                        target=step_data.get("target", ""),
                        value=step_data.get("value"),
                        expected_outcome=step_data.get("expected_outcome"),
                    )
                    test_steps.append(step)
                
                # Create scenario
                scenario = TestScenario(
                    id=scenario_data.get("id", str(uuid.uuid4())),
                    criterion_id=scenario_data.get("criterion_id", ""),
                    type=ScenarioType(scenario_data.get("type")),
                    priority=Priority(scenario_data.get("priority", "medium")),
                    given=scenario_data.get("given", []),
                    when=scenario_data.get("when", []),
                    then=scenario_data.get("then", []),
                    test_steps=test_steps,
                )
                scenarios.append(scenario)
            
            # Detect dependencies between scenarios
            scenarios = self._enhance_with_dependencies(scenarios, criteria)
            
            # Assign/refine priorities based on business impact
            scenarios = self.assign_priorities(scenarios)
            
            logger.info(
                "scenario_generation_completed",
                extra={
                    "scenarios_count": len(scenarios),
                    "positive_count": sum(1 for s in scenarios if s.type == ScenarioType.POSITIVE),
                    "negative_count": sum(1 for s in scenarios if s.type == ScenarioType.NEGATIVE),
                    "edge_case_count": sum(1 for s in scenarios if s.type == ScenarioType.EDGE_CASE),
                }
            )
            
            return scenarios
            
        except LLMException as e:
            logger.error(
                "scenario_generation_llm_error",
                extra={
                    "error": str(e),
                }
            )
            
            raise ScenarioGenerationException(
                f"LLM error during scenario generation: {str(e)}",
                original_exception=e,
            )
        
        except Exception as e:
            logger.error(
                "scenario_generation_unexpected_error",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                }
            )
            
            raise ScenarioGenerationException(
                f"Unexpected error during scenario generation: {str(e)}",
                original_exception=e,
            )
    
    def _enhance_with_dependencies(
        self,
        scenarios: list[TestScenario],
        criteria: list[AcceptanceCriterion],
    ) -> list[TestScenario]:
        """
        Enhance scenarios with dependency information from criteria.
        
        This method maps criterion dependencies to scenario dependencies,
        ensuring that scenarios testing dependent criteria are aware of
        their dependencies.
        
        Args:
            scenarios: List of generated scenarios
            criteria: Original acceptance criteria with dependencies
        
        Returns:
            list[TestScenario]: Scenarios with enhanced dependency information
        
        Requirements: 2.4
        """
        # Build criterion dependency map
        criterion_deps = {c.id: c.dependencies for c in criteria}
        
        # Group scenarios by criterion
        scenarios_by_criterion = defaultdict(list)
        for scenario in scenarios:
            scenarios_by_criterion[scenario.criterion_id].append(scenario)
        
        # Note: TestScenario model doesn't have dependencies field in current schema
        # This is metadata that would be used by the execution engine
        # For now, we log the dependency information
        
        for criterion_id, deps in criterion_deps.items():
            if deps:
                logger.debug(
                    "criterion_dependencies_detected",
                    extra={
                        "criterion_id": criterion_id,
                        "depends_on": deps,
                        "scenario_count": len(scenarios_by_criterion[criterion_id]),
                    }
                )
        
        return scenarios
    
    def detect_dependencies(
        self,
        scenarios: list[TestScenario],
    ) -> DependencyGraph:
        """
        Identify scenario execution order requirements.
        
        This method analyzes scenarios to detect dependencies based on:
        - Criterion dependencies
        - Scenario types (positive scenarios typically run before negative)
        - Test step analysis (scenarios that create data vs. scenarios that use data)
        
        Args:
            scenarios: List of test scenarios
        
        Returns:
            DependencyGraph: Graph representing scenario dependencies
        
        Requirements: 2.4
        """
        graph = DependencyGraph()
        
        # Group scenarios by criterion
        scenarios_by_criterion = defaultdict(list)
        for scenario in scenarios:
            scenarios_by_criterion[scenario.criterion_id].append(scenario)
        
        # Rule 1: Positive scenarios should run before negative/edge cases
        # for the same criterion
        for criterion_id, criterion_scenarios in scenarios_by_criterion.items():
            positive_scenarios = [s for s in criterion_scenarios if s.type == ScenarioType.POSITIVE]
            other_scenarios = [s for s in criterion_scenarios if s.type != ScenarioType.POSITIVE]
            
            for positive in positive_scenarios:
                for other in other_scenarios:
                    graph.add_dependency(other.id, positive.id)
        
        # Rule 2: Scenarios that create/setup data should run before scenarios that use it
        # Detect by analyzing test steps
        setup_scenarios = []
        usage_scenarios = []
        
        for scenario in scenarios:
            has_create_actions = any(
                step.action in [ActionType.TYPE, ActionType.CLICK]
                and any(keyword in step.target.lower() for keyword in ["create", "add", "new", "register", "signup"])
                for step in scenario.test_steps
            )
            
            has_usage_actions = any(
                step.action == ActionType.ASSERT
                or (step.action == ActionType.CLICK and "delete" in step.target.lower())
                for step in scenario.test_steps
            )
            
            if has_create_actions:
                setup_scenarios.append(scenario)
            elif has_usage_actions:
                usage_scenarios.append(scenario)
        
        # Setup scenarios should run before usage scenarios
        for setup in setup_scenarios:
            for usage in usage_scenarios:
                if setup.criterion_id != usage.criterion_id:
                    graph.add_dependency(usage.id, setup.id)
        
        logger.debug(
            "dependency_detection_completed",
            extra={
                "total_scenarios": len(scenarios),
                "dependencies_count": sum(len(deps) for deps in graph.dependencies.values()),
            }
        )
        
        return graph
    
    def assign_priorities(
        self,
        scenarios: list[TestScenario],
    ) -> list[TestScenario]:
        """
        Assign priority levels based on business impact.
        
        This method analyzes scenarios and assigns/refines priorities based on:
        - Scenario type (positive flows are typically higher priority)
        - Test step complexity
        - Keywords indicating critical functionality
        
        Args:
            scenarios: List of test scenarios
        
        Returns:
            list[TestScenario]: Scenarios with assigned priorities
        
        Requirements: 2.7
        """
        critical_keywords = [
            "login", "authentication", "payment", "checkout", "security",
            "data loss", "corruption", "crash", "error", "failure"
        ]
        
        high_keywords = [
            "create", "delete", "update", "save", "submit", "validation",
            "required", "mandatory"
        ]
        
        for scenario in scenarios:
            # Start with existing priority
            current_priority = scenario.priority
            
            # Combine all text for analysis
            all_text = " ".join(
                scenario.given + scenario.when + scenario.then +
                [step.target for step in scenario.test_steps] +
                [step.expected_outcome or "" for step in scenario.test_steps]
            ).lower()
            
            # Check for critical keywords
            if any(keyword in all_text for keyword in critical_keywords):
                if current_priority != Priority.CRITICAL:
                    logger.debug(
                        "scenario_priority_elevated_to_critical",
                        extra={
                            "scenario_id": scenario.id,
                            "original_priority": current_priority.value,
                        }
                    )
                    scenario.priority = Priority.CRITICAL
                continue
            
            # Check for high priority keywords
            if any(keyword in all_text for keyword in high_keywords):
                if current_priority not in [Priority.CRITICAL, Priority.HIGH]:
                    logger.debug(
                        "scenario_priority_elevated_to_high",
                        extra={
                            "scenario_id": scenario.id,
                            "original_priority": current_priority.value,
                        }
                    )
                    scenario.priority = Priority.HIGH
                continue
            
            # Positive scenarios are generally higher priority than negative/edge
            if scenario.type == ScenarioType.POSITIVE:
                if current_priority == Priority.LOW:
                    scenario.priority = Priority.MEDIUM
            elif scenario.type == ScenarioType.EDGE_CASE:
                # Edge cases are generally lower priority unless marked otherwise
                if current_priority == Priority.CRITICAL:
                    scenario.priority = Priority.HIGH
        
        # Log priority distribution
        priority_counts = defaultdict(int)
        for scenario in scenarios:
            priority_counts[scenario.priority.value] += 1
        
        logger.info(
            "scenario_priorities_assigned",
            extra={
                "priority_distribution": dict(priority_counts),
            }
        )
        
        return scenarios
