"""
Schema validators for parsed story data.

This module provides comprehensive validation for parsed stories,
acceptance criteria, and test scenarios using Pydantic validation
with custom business rules.
"""

from typing import Optional, Any
from pydantic import ValidationError

from app.models.story import (
    ParsedStory,
    AcceptanceCriterion,
    StoryInput,
)
from app.models.test_scenario import (
    TestScenario,
    TestStep,
    ScenarioType,
    ActionType,
)
from app.core.exceptions import ValidationException
from app.core.logging import get_logger


logger = get_logger(__name__)


class ValidationResult:
    """Result of validation with detailed error information."""
    
    def __init__(
        self,
        is_valid: bool,
        errors: list[str],
        warnings: list[str],
        field_errors: Optional[dict[str, list[str]]] = None,
    ):
        """
        Initialize validation result.
        
        Args:
            is_valid: Whether validation passed
            errors: List of error messages
            warnings: List of warning messages
            field_errors: Field-specific errors
        """
        self.is_valid = is_valid
        self.errors = errors
        self.warnings = warnings
        self.field_errors = field_errors or {}
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "field_errors": self.field_errors,
        }
    
    def __bool__(self) -> bool:
        """Allow using result in boolean context."""
        return self.is_valid


class StoryValidator:
    """
    Validator for parsed stories with business rules.
    
    This validator checks:
    - Pydantic schema compliance
    - Business rule compliance
    - Data quality and completeness
    - Cross-field validation
    
    Requirements: 1.5
    """
    
    @staticmethod
    def validate_story_input(story_input: StoryInput) -> ValidationResult:
        """
        Validate story input before parsing.
        
        Args:
            story_input: The story input to validate
        
        Returns:
            ValidationResult: Validation result
        """
        errors = []
        warnings = []
        field_errors = {}
        
        try:
            # Pydantic validation is automatic, but we can add custom checks
            
            # Check text length
            if len(story_input.text) < 50:
                warnings.append("Story text is very short - may lack sufficient detail")
            
            if len(story_input.text) > 5000:
                warnings.append("Story text is very long - consider breaking into multiple stories")
            
            # Check for common story format indicators
            text_lower = story_input.text.lower()
            
            if "as a" not in text_lower and "as an" not in text_lower:
                warnings.append("Story doesn't contain 'As a' - may not follow standard format")
            
            if "i want" not in text_lower:
                warnings.append("Story doesn't contain 'I want' - may not follow standard format")
            
            if "so that" not in text_lower:
                warnings.append("Story doesn't contain 'So that' - benefit may not be clear")
            
            # Check for acceptance criteria indicators
            has_criteria_indicators = any(
                indicator in text_lower
                for indicator in [
                    "acceptance criteria",
                    "given",
                    "when",
                    "then",
                    "1.",
                    "2.",
                    "-",
                    "*",
                ]
            )
            
            if not has_criteria_indicators:
                warnings.append("No clear acceptance criteria indicators found")
            
        except ValidationError as e:
            for error in e.errors():
                field = ".".join(str(loc) for loc in error["loc"])
                message = error["msg"]
                
                if field not in field_errors:
                    field_errors[field] = []
                field_errors[field].append(message)
                errors.append(f"{field}: {message}")
        
        is_valid = len(errors) == 0
        
        logger.debug(
            "story_input_validated",
            extra={
                "is_valid": is_valid,
                "errors_count": len(errors),
                "warnings_count": len(warnings),
            }
        )
        
        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            field_errors=field_errors,
        )
    
    @staticmethod
    def validate_parsed_story(story: ParsedStory) -> ValidationResult:
        """
        Validate parsed story with business rules.
        
        Args:
            story: The parsed story to validate
        
        Returns:
            ValidationResult: Validation result
        """
        errors = []
        warnings = []
        field_errors = {}
        
        try:
            # Pydantic validation happens automatically
            
            # Business rule: Must have at least one acceptance criterion
            if not story.acceptance_criteria:
                errors.append("Story must have at least one acceptance criterion")
                field_errors["acceptance_criteria"] = ["At least one criterion required"]
            
            # Business rule: Title should be descriptive
            if len(story.title) < 5:
                warnings.append("Story title is very short")
            
            if len(story.title) > 100:
                warnings.append("Story title is very long - consider shortening")
            
            # Business rule: Role should be specific
            generic_roles = ["user", "person", "someone", "anybody"]
            if story.role.lower() in generic_roles:
                warnings.append(f"Role '{story.role}' is generic - consider being more specific")
            
            # Business rule: Feature should be actionable
            if len(story.feature) < 10:
                warnings.append("Feature description is very short")
            
            # Business rule: Benefit should be clear
            if len(story.benefit) < 10:
                warnings.append("Benefit description is very short")
            
            # Validate acceptance criteria
            criterion_ids = set()
            for idx, criterion in enumerate(story.acceptance_criteria):
                # Check for duplicate IDs
                if criterion.id in criterion_ids:
                    errors.append(f"Duplicate acceptance criterion ID: {criterion.id}")
                    if "acceptance_criteria" not in field_errors:
                        field_errors["acceptance_criteria"] = []
                    field_errors["acceptance_criteria"].append(f"Duplicate ID: {criterion.id}")
                criterion_ids.add(criterion.id)
                
                # Validate criterion text length
                if len(criterion.text) < 10:
                    warnings.append(f"Acceptance criterion {criterion.id} is very short")
                
                # Check for invalid dependencies
                for dep_id in criterion.dependencies:
                    if dep_id not in criterion_ids and dep_id != criterion.id:
                        # Dependency might be defined later, so just warn
                        warnings.append(
                            f"Criterion {criterion.id} depends on {dep_id} which may not exist"
                        )
            
            # Check for circular dependencies
            if StoryValidator._has_circular_dependencies(story.acceptance_criteria):
                errors.append("Circular dependencies detected in acceptance criteria")
                field_errors["acceptance_criteria"] = ["Circular dependencies not allowed"]
            
            # Warn about ambiguities
            if story.ambiguities:
                warnings.append(
                    f"Story has {len(story.ambiguities)} ambiguities that should be clarified"
                )
            
            # Recommend implicit requirements
            if not story.implicit_requirements:
                warnings.append(
                    "No implicit requirements identified - consider security, performance, accessibility"
                )
            
        except ValidationError as e:
            for error in e.errors():
                field = ".".join(str(loc) for loc in error["loc"])
                message = error["msg"]
                
                if field not in field_errors:
                    field_errors[field] = []
                field_errors[field].append(message)
                errors.append(f"{field}: {message}")
        
        is_valid = len(errors) == 0
        
        logger.debug(
            "parsed_story_validated",
            extra={
                "story_id": story.id,
                "is_valid": is_valid,
                "errors_count": len(errors),
                "warnings_count": len(warnings),
            }
        )
        
        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            field_errors=field_errors,
        )
    
    @staticmethod
    def _has_circular_dependencies(criteria: list[AcceptanceCriterion]) -> bool:
        """
        Check for circular dependencies in acceptance criteria.
        
        Uses depth-first search to detect cycles.
        
        Args:
            criteria: List of acceptance criteria
        
        Returns:
            bool: True if circular dependencies exist
        """
        # Build adjacency list
        graph = {c.id: c.dependencies for c in criteria}
        
        # Track visited nodes and recursion stack
        visited = set()
        rec_stack = set()
        
        def has_cycle(node: str) -> bool:
            """DFS to detect cycle."""
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    if has_cycle(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            
            rec_stack.remove(node)
            return False
        
        # Check each node
        for criterion in criteria:
            if criterion.id not in visited:
                if has_cycle(criterion.id):
                    return True
        
        return False


class ScenarioValidator:
    """
    Validator for test scenarios with business rules.
    
    Requirements: 1.5
    """
    
    @staticmethod
    def validate_scenario(scenario: TestScenario) -> ValidationResult:
        """
        Validate test scenario with business rules.
        
        Args:
            scenario: The test scenario to validate
        
        Returns:
            ValidationResult: Validation result
        """
        errors = []
        warnings = []
        field_errors = {}
        
        try:
            # Pydantic validation happens automatically
            
            # Business rule: Must have at least one Given-When-Then statement
            if not scenario.given:
                errors.append("Scenario must have at least one Given statement")
                field_errors["given"] = ["At least one Given statement required"]
            
            if not scenario.when:
                errors.append("Scenario must have at least one When statement")
                field_errors["when"] = ["At least one When statement required"]
            
            if not scenario.then:
                errors.append("Scenario must have at least one Then statement")
                field_errors["then"] = ["At least one Then statement required"]
            
            # Business rule: Must have test steps
            if not scenario.test_steps:
                errors.append("Scenario must have at least one test step")
                field_errors["test_steps"] = ["At least one test step required"]
            
            # Validate test steps
            for idx, step in enumerate(scenario.test_steps):
                step_errors = ScenarioValidator._validate_test_step(step, idx)
                if step_errors:
                    if "test_steps" not in field_errors:
                        field_errors["test_steps"] = []
                    field_errors["test_steps"].extend(step_errors)
                    errors.extend(step_errors)
            
            # Business rule: Positive scenarios should have assertions
            if scenario.type == ScenarioType.POSITIVE:
                has_assertions = any(
                    step.action == ActionType.ASSERT
                    for step in scenario.test_steps
                )
                if not has_assertions:
                    warnings.append("Positive scenario should include assertion steps")
            
            # Business rule: Negative scenarios should test error handling
            if scenario.type == ScenarioType.NEGATIVE:
                has_error_checks = any(
                    step.action == ActionType.ASSERT and
                    step.expected_outcome and
                    any(keyword in step.expected_outcome.lower() for keyword in ["error", "fail", "invalid", "warning"])
                    for step in scenario.test_steps
                )
                if not has_error_checks:
                    warnings.append("Negative scenario should verify error handling")
            
            # Warn about scenario length
            if len(scenario.test_steps) > 20:
                warnings.append("Scenario has many steps - consider breaking into smaller scenarios")
            
        except ValidationError as e:
            for error in e.errors():
                field = ".".join(str(loc) for loc in error["loc"])
                message = error["msg"]
                
                if field not in field_errors:
                    field_errors[field] = []
                field_errors[field].append(message)
                errors.append(f"{field}: {message}")
        
        is_valid = len(errors) == 0
        
        logger.debug(
            "scenario_validated",
            extra={
                "scenario_id": scenario.id,
                "is_valid": is_valid,
                "errors_count": len(errors),
                "warnings_count": len(warnings),
            }
        )
        
        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            field_errors=field_errors,
        )
    
    @staticmethod
    def _validate_test_step(step: TestStep, index: int) -> list[str]:
        """
        Validate individual test step.
        
        Args:
            step: The test step to validate
            index: Step index in scenario
        
        Returns:
            list[str]: List of error messages
        """
        errors = []
        
        # Business rule: Type action must have value
        if step.action == ActionType.TYPE and not step.value:
            errors.append(f"Step {index + 1}: TYPE action must have a value")
        
        # Business rule: Select action must have value
        if step.action == ActionType.SELECT and not step.value:
            errors.append(f"Step {index + 1}: SELECT action must have a value")
        
        # Business rule: Assert action should have expected outcome
        if step.action == ActionType.ASSERT and not step.expected_outcome:
            errors.append(f"Step {index + 1}: ASSERT action should have expected_outcome")
        
        # Business rule: Navigate action target should look like URL or page name
        if step.action == ActionType.NAVIGATE:
            if not step.target:
                errors.append(f"Step {index + 1}: NAVIGATE action must have target")
        
        # Business rule: Target should be descriptive
        if len(step.target) < 3:
            errors.append(f"Step {index + 1}: Target description is too short")
        
        return errors
    
    @staticmethod
    def validate_scenarios_batch(scenarios: list[TestScenario]) -> ValidationResult:
        """
        Validate a batch of scenarios with cross-scenario checks.
        
        Args:
            scenarios: List of scenarios to validate
        
        Returns:
            ValidationResult: Validation result
        """
        errors = []
        warnings = []
        field_errors = {}
        
        # Validate each scenario individually
        for scenario in scenarios:
            result = ScenarioValidator.validate_scenario(scenario)
            if not result.is_valid:
                errors.extend(result.errors)
                for field, field_errs in result.field_errors.items():
                    key = f"{scenario.id}.{field}"
                    field_errors[key] = field_errs
            warnings.extend(result.warnings)
        
        # Cross-scenario validation
        scenario_ids = set()
        for scenario in scenarios:
            if scenario.id in scenario_ids:
                errors.append(f"Duplicate scenario ID: {scenario.id}")
            scenario_ids.add(scenario.id)
        
        # Check coverage by criterion
        criteria_coverage = {}
        for scenario in scenarios:
            if scenario.criterion_id not in criteria_coverage:
                criteria_coverage[scenario.criterion_id] = []
            criteria_coverage[scenario.criterion_id].append(scenario.type)
        
        # Warn about criteria with only one scenario type
        for criterion_id, types in criteria_coverage.items():
            unique_types = set(types)
            if len(unique_types) == 1:
                warnings.append(
                    f"Criterion {criterion_id} only has {types[0].value} scenarios - "
                    "consider adding other scenario types"
                )
        
        is_valid = len(errors) == 0
        
        logger.info(
            "scenarios_batch_validated",
            extra={
                "scenarios_count": len(scenarios),
                "is_valid": is_valid,
                "errors_count": len(errors),
                "warnings_count": len(warnings),
            }
        )
        
        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            field_errors=field_errors,
        )


def validate_story_input(story_input: StoryInput) -> ValidationResult:
    """
    Convenience function to validate story input.
    
    Args:
        story_input: The story input to validate
    
    Returns:
        ValidationResult: Validation result
        
    Raises:
        ValidationException: If validation fails critically
    """
    result = StoryValidator.validate_story_input(story_input)
    
    if not result.is_valid:
        logger.warning(
            "story_input_validation_failed",
            extra={
                "errors": result.errors,
            }
        )
    
    return result


def validate_parsed_story(story: ParsedStory, raise_on_error: bool = False) -> ValidationResult:
    """
    Convenience function to validate parsed story.
    
    Args:
        story: The parsed story to validate
        raise_on_error: If True, raise exception on validation failure
    
    Returns:
        ValidationResult: Validation result
        
    Raises:
        ValidationException: If validation fails and raise_on_error is True
    """
    result = StoryValidator.validate_parsed_story(story)
    
    if not result.is_valid:
        logger.warning(
            "parsed_story_validation_failed",
            extra={
                "story_id": story.id,
                "errors": result.errors,
            }
        )
        
        if raise_on_error:
            raise ValidationException(
                "Parsed story validation failed",
                validation_errors=result.errors,
            )
    
    return result


def validate_scenario(scenario: TestScenario, raise_on_error: bool = False) -> ValidationResult:
    """
    Convenience function to validate test scenario.
    
    Args:
        scenario: The test scenario to validate
        raise_on_error: If True, raise exception on validation failure
    
    Returns:
        ValidationResult: Validation result
        
    Raises:
        ValidationException: If validation fails and raise_on_error is True
    """
    result = ScenarioValidator.validate_scenario(scenario)
    
    if not result.is_valid:
        logger.warning(
            "scenario_validation_failed",
            extra={
                "scenario_id": scenario.id,
                "errors": result.errors,
            }
        )
        
        if raise_on_error:
            raise ValidationException(
                "Test scenario validation failed",
                validation_errors=result.errors,
            )
    
    return result


def validate_scenarios_batch(
    scenarios: list[TestScenario],
    raise_on_error: bool = False
) -> ValidationResult:
    """
    Convenience function to validate batch of scenarios.
    
    Args:
        scenarios: List of scenarios to validate
        raise_on_error: If True, raise exception on validation failure
    
    Returns:
        ValidationResult: Validation result
        
    Raises:
        ValidationException: If validation fails and raise_on_error is True
    """
    result = ScenarioValidator.validate_scenarios_batch(scenarios)
    
    if not result.is_valid:
        logger.warning(
            "scenarios_batch_validation_failed",
            extra={
                "scenarios_count": len(scenarios),
                "errors": result.errors,
            }
        )
        
        if raise_on_error:
            raise ValidationException(
                "Scenarios batch validation failed",
                validation_errors=result.errors,
            )
    
    return result
