"""
Smart waiting strategies for dynamic content handling.

This module implements intelligent waiting strategies that handle
dynamic content loading, AJAX requests, and DOM mutations without
relying on fixed timeouts.

Requirements: 3.7
"""

import asyncio
from typing import Optional, Callable, Any
from enum import Enum
from dataclasses import dataclass
from playwright.async_api import Page, Locator

from app.core.exceptions import TimeoutException
from app.core.logging import get_logger


logger = get_logger(__name__)


class WaitStrategy(str, Enum):
    """Types of waiting strategies."""
    ELEMENT_VISIBLE = "element_visible"
    ELEMENT_HIDDEN = "element_hidden"
    ELEMENT_STABLE = "element_stable"
    NETWORK_IDLE = "network_idle"
    DOM_CONTENT_LOADED = "dom_content_loaded"
    LOAD = "load"
    CUSTOM_CONDITION = "custom_condition"
    MUTATION_OBSERVER = "mutation_observer"


@dataclass
class WaitConfig:
    """Configuration for waiting strategies."""
    timeout_ms: int = 30000  # Default 30 seconds
    poll_interval_ms: int = 100  # Poll every 100ms
    stability_duration_ms: int = 500  # Element must be stable for 500ms
    network_idle_duration_ms: int = 500  # Network must be idle for 500ms


class SmartWaiter:
    """
    Smart waiting strategies for dynamic content.
    
    This class provides intelligent waiting mechanisms that adapt to
    different types of dynamic content loading patterns:
    - Polling for element visibility/state changes
    - Mutation observers for DOM changes
    - Network idle detection for AJAX requests
    - Element stability detection for animations
    
    Requirements: 3.7
    """
    
    def __init__(self, config: Optional[WaitConfig] = None):
        """
        Initialize the smart waiter.
        
        Args:
            config: Optional wait configuration (uses defaults if None)
        """
        self.config = config or WaitConfig()
    
    async def wait_for_element_visible(
        self,
        locator: Locator,
        timeout_ms: Optional[int] = None
    ) -> bool:
        """
        Wait for an element to become visible.
        
        Args:
            locator: Playwright locator for the element
            timeout_ms: Optional timeout override
            
        Returns:
            True if element became visible, False otherwise
            
        Raises:
            TimeoutException: If element doesn't become visible within timeout
        """
        timeout = timeout_ms or self.config.timeout_ms
        
        logger.debug(
            "waiting_for_element_visible",
            extra={
                "timeout_ms": timeout
            }
        )
        
        try:
            await locator.wait_for(state="visible", timeout=timeout)
            logger.debug("element_became_visible")
            return True
        except Exception as e:
            logger.error(
                "element_visibility_timeout",
                extra={
                    "timeout_ms": timeout,
                    "error": str(e)
                }
            )
            raise TimeoutException(
                f"Element did not become visible within {timeout}ms",
                timeout_ms=timeout,
                original_exception=e
            )
    
    async def wait_for_element_hidden(
        self,
        locator: Locator,
        timeout_ms: Optional[int] = None
    ) -> bool:
        """
        Wait for an element to become hidden.
        
        Args:
            locator: Playwright locator for the element
            timeout_ms: Optional timeout override
            
        Returns:
            True if element became hidden, False otherwise
            
        Raises:
            TimeoutException: If element doesn't become hidden within timeout
        """
        timeout = timeout_ms or self.config.timeout_ms
        
        logger.debug(
            "waiting_for_element_hidden",
            extra={
                "timeout_ms": timeout
            }
        )
        
        try:
            await locator.wait_for(state="hidden", timeout=timeout)
            logger.debug("element_became_hidden")
            return True
        except Exception as e:
            logger.error(
                "element_hidden_timeout",
                extra={
                    "timeout_ms": timeout,
                    "error": str(e)
                }
            )
            raise TimeoutException(
                f"Element did not become hidden within {timeout}ms",
                timeout_ms=timeout,
                original_exception=e
            )
    
    async def wait_for_element_stable(
        self,
        locator: Locator,
        timeout_ms: Optional[int] = None,
        stability_duration_ms: Optional[int] = None
    ) -> bool:
        """
        Wait for an element to become stable (no position/size changes).
        
        This is useful for waiting for animations to complete.
        
        Args:
            locator: Playwright locator for the element
            timeout_ms: Optional timeout override
            stability_duration_ms: How long element must be stable
            
        Returns:
            True if element became stable, False otherwise
            
        Raises:
            TimeoutException: If element doesn't stabilize within timeout
            
        Requirements: 3.7
        """
        timeout = timeout_ms or self.config.timeout_ms
        stability_duration = stability_duration_ms or self.config.stability_duration_ms
        
        logger.debug(
            "waiting_for_element_stable",
            extra={
                "timeout_ms": timeout,
                "stability_duration_ms": stability_duration
            }
        )
        
        start_time = asyncio.get_event_loop().time()
        last_box = None
        stable_since = None
        
        while True:
            current_time = asyncio.get_event_loop().time()
            elapsed_ms = (current_time - start_time) * 1000
            
            if elapsed_ms > timeout:
                raise TimeoutException(
                    f"Element did not stabilize within {timeout}ms",
                    timeout_ms=timeout
                )
            
            try:
                # Get current bounding box
                current_box = await locator.bounding_box()
                
                if current_box is None:
                    # Element not visible, reset stability
                    last_box = None
                    stable_since = None
                elif last_box is None:
                    # First time seeing element
                    last_box = current_box
                    stable_since = current_time
                elif self._boxes_equal(last_box, current_box):
                    # Element hasn't moved
                    stable_duration_actual = (current_time - stable_since) * 1000
                    
                    if stable_duration_actual >= stability_duration:
                        logger.debug(
                            "element_became_stable",
                            extra={
                                "stable_duration_ms": stable_duration_actual
                            }
                        )
                        return True
                else:
                    # Element moved, reset stability timer
                    last_box = current_box
                    stable_since = current_time
                
                # Wait before next check
                await asyncio.sleep(self.config.poll_interval_ms / 1000)
                
            except Exception as e:
                logger.error(
                    "element_stability_check_failed",
                    extra={
                        "error": str(e)
                    }
                )
                await asyncio.sleep(self.config.poll_interval_ms / 1000)
    
    async def wait_for_network_idle(
        self,
        page: Page,
        timeout_ms: Optional[int] = None,
        idle_duration_ms: Optional[int] = None
    ) -> bool:
        """
        Wait for network to become idle (no pending requests).
        
        This is useful for waiting for AJAX requests to complete.
        
        Args:
            page: Playwright page object
            timeout_ms: Optional timeout override
            idle_duration_ms: How long network must be idle
            
        Returns:
            True if network became idle, False otherwise
            
        Raises:
            TimeoutException: If network doesn't become idle within timeout
            
        Requirements: 3.7
        """
        timeout = timeout_ms or self.config.timeout_ms
        idle_duration = idle_duration_ms or self.config.network_idle_duration_ms
        
        logger.debug(
            "waiting_for_network_idle",
            extra={
                "timeout_ms": timeout,
                "idle_duration_ms": idle_duration
            }
        )
        
        try:
            # Use Playwright's built-in network idle waiting
            await page.wait_for_load_state("networkidle", timeout=timeout)
            logger.debug("network_became_idle")
            return True
        except Exception as e:
            logger.error(
                "network_idle_timeout",
                extra={
                    "timeout_ms": timeout,
                    "error": str(e)
                }
            )
            raise TimeoutException(
                f"Network did not become idle within {timeout}ms",
                timeout_ms=timeout,
                original_exception=e
            )
    
    async def wait_for_dom_content_loaded(
        self,
        page: Page,
        timeout_ms: Optional[int] = None
    ) -> bool:
        """
        Wait for DOM content to be loaded.
        
        Args:
            page: Playwright page object
            timeout_ms: Optional timeout override
            
        Returns:
            True if DOM content loaded, False otherwise
            
        Raises:
            TimeoutException: If DOM content doesn't load within timeout
        """
        timeout = timeout_ms or self.config.timeout_ms
        
        logger.debug(
            "waiting_for_dom_content_loaded",
            extra={
                "timeout_ms": timeout
            }
        )
        
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=timeout)
            logger.debug("dom_content_loaded")
            return True
        except Exception as e:
            logger.error(
                "dom_content_loaded_timeout",
                extra={
                    "timeout_ms": timeout,
                    "error": str(e)
                }
            )
            raise TimeoutException(
                f"DOM content did not load within {timeout}ms",
                timeout_ms=timeout,
                original_exception=e
            )
    
    async def wait_for_page_load(
        self,
        page: Page,
        timeout_ms: Optional[int] = None
    ) -> bool:
        """
        Wait for page to fully load (including all resources).
        
        Args:
            page: Playwright page object
            timeout_ms: Optional timeout override
            
        Returns:
            True if page loaded, False otherwise
            
        Raises:
            TimeoutException: If page doesn't load within timeout
        """
        timeout = timeout_ms or self.config.timeout_ms
        
        logger.debug(
            "waiting_for_page_load",
            extra={
                "timeout_ms": timeout
            }
        )
        
        try:
            await page.wait_for_load_state("load", timeout=timeout)
            logger.debug("page_loaded")
            return True
        except Exception as e:
            logger.error(
                "page_load_timeout",
                extra={
                    "timeout_ms": timeout,
                    "error": str(e)
                }
            )
            raise TimeoutException(
                f"Page did not load within {timeout}ms",
                timeout_ms=timeout,
                original_exception=e
            )
    
    async def wait_for_condition(
        self,
        condition: Callable[[], Any],
        timeout_ms: Optional[int] = None,
        poll_interval_ms: Optional[int] = None,
        error_message: str = "Condition not met within timeout"
    ) -> bool:
        """
        Wait for a custom condition to become true.
        
        Args:
            condition: Async or sync callable that returns truthy value when condition is met
            timeout_ms: Optional timeout override
            poll_interval_ms: Optional poll interval override
            error_message: Custom error message for timeout
            
        Returns:
            True if condition was met, False otherwise
            
        Raises:
            TimeoutException: If condition is not met within timeout
            
        Requirements: 3.7
        """
        timeout = timeout_ms or self.config.timeout_ms
        poll_interval = poll_interval_ms or self.config.poll_interval_ms
        
        logger.debug(
            "waiting_for_custom_condition",
            extra={
                "timeout_ms": timeout,
                "poll_interval_ms": poll_interval
            }
        )
        
        start_time = asyncio.get_event_loop().time()
        
        while True:
            current_time = asyncio.get_event_loop().time()
            elapsed_ms = (current_time - start_time) * 1000
            
            if elapsed_ms > timeout:
                logger.error(
                    "custom_condition_timeout",
                    extra={
                        "timeout_ms": timeout,
                        "elapsed_ms": elapsed_ms
                    }
                )
                raise TimeoutException(
                    error_message,
                    timeout_ms=timeout
                )
            
            try:
                # Check condition (handle both async and sync)
                if asyncio.iscoroutinefunction(condition):
                    result = await condition()
                else:
                    result = condition()
                
                if result:
                    logger.debug(
                        "custom_condition_met",
                        extra={
                            "elapsed_ms": elapsed_ms
                        }
                    )
                    return True
                
            except Exception as e:
                logger.warning(
                    "custom_condition_check_failed",
                    extra={
                        "error": str(e)
                    }
                )
            
            # Wait before next check
            await asyncio.sleep(poll_interval / 1000)
    
    async def wait_for_dom_mutation(
        self,
        page: Page,
        selector: str,
        mutation_type: str = "childList",
        timeout_ms: Optional[int] = None
    ) -> bool:
        """
        Wait for DOM mutations using MutationObserver.
        
        This is useful for detecting when dynamic content is added to the page.
        
        Args:
            page: Playwright page object
            selector: CSS selector for element to observe
            mutation_type: Type of mutation to watch for (childList, attributes, characterData)
            timeout_ms: Optional timeout override
            
        Returns:
            True if mutation detected, False otherwise
            
        Raises:
            TimeoutException: If mutation doesn't occur within timeout
            
        Requirements: 3.7
        """
        timeout = timeout_ms or self.config.timeout_ms
        
        logger.debug(
            "waiting_for_dom_mutation",
            extra={
                "selector": selector,
                "mutation_type": mutation_type,
                "timeout_ms": timeout
            }
        )
        
        try:
            # Set up mutation observer in the page
            mutation_detected = await page.evaluate(f"""
                new Promise((resolve, reject) => {{
                    const timeout = setTimeout(() => {{
                        observer.disconnect();
                        reject(new Error('Mutation timeout'));
                    }}, {timeout});
                    
                    const targetNode = document.querySelector('{selector}');
                    if (!targetNode) {{
                        clearTimeout(timeout);
                        reject(new Error('Target element not found'));
                        return;
                    }}
                    
                    const config = {{
                        {mutation_type}: true,
                        subtree: true
                    }};
                    
                    const observer = new MutationObserver((mutations) => {{
                        if (mutations.length > 0) {{
                            clearTimeout(timeout);
                            observer.disconnect();
                            resolve(true);
                        }}
                    }});
                    
                    observer.observe(targetNode, config);
                }})
            """)
            
            logger.debug(
                "dom_mutation_detected",
                extra={
                    "selector": selector,
                    "mutation_type": mutation_type
                }
            )
            
            return mutation_detected
            
        except Exception as e:
            logger.error(
                "dom_mutation_timeout",
                extra={
                    "selector": selector,
                    "mutation_type": mutation_type,
                    "timeout_ms": timeout,
                    "error": str(e)
                }
            )
            raise TimeoutException(
                f"DOM mutation not detected within {timeout}ms",
                timeout_ms=timeout,
                step_description=f"Waiting for mutation on {selector}",
                original_exception=e
            )
    
    async def smart_wait(
        self,
        page: Page,
        locator: Optional[Locator] = None,
        strategy: WaitStrategy = WaitStrategy.ELEMENT_VISIBLE,
        timeout_ms: Optional[int] = None
    ) -> bool:
        """
        Intelligent wait that chooses the best strategy based on context.
        
        This is a convenience method that selects the appropriate waiting
        strategy based on the situation.
        
        Args:
            page: Playwright page object
            locator: Optional locator for element-based waits
            strategy: Wait strategy to use
            timeout_ms: Optional timeout override
            
        Returns:
            True if wait condition was met
            
        Raises:
            TimeoutException: If wait condition is not met within timeout
        """
        logger.debug(
            "smart_wait_started",
            extra={
                "strategy": strategy.value,
                "timeout_ms": timeout_ms or self.config.timeout_ms
            }
        )
        
        if strategy == WaitStrategy.ELEMENT_VISIBLE:
            if not locator:
                raise ValueError("Locator required for ELEMENT_VISIBLE strategy")
            return await self.wait_for_element_visible(locator, timeout_ms)
        
        elif strategy == WaitStrategy.ELEMENT_HIDDEN:
            if not locator:
                raise ValueError("Locator required for ELEMENT_HIDDEN strategy")
            return await self.wait_for_element_hidden(locator, timeout_ms)
        
        elif strategy == WaitStrategy.ELEMENT_STABLE:
            if not locator:
                raise ValueError("Locator required for ELEMENT_STABLE strategy")
            return await self.wait_for_element_stable(locator, timeout_ms)
        
        elif strategy == WaitStrategy.NETWORK_IDLE:
            return await self.wait_for_network_idle(page, timeout_ms)
        
        elif strategy == WaitStrategy.DOM_CONTENT_LOADED:
            return await self.wait_for_dom_content_loaded(page, timeout_ms)
        
        elif strategy == WaitStrategy.LOAD:
            return await self.wait_for_page_load(page, timeout_ms)
        
        else:
            raise ValueError(f"Unsupported wait strategy: {strategy}")
    
    def _boxes_equal(
        self,
        box1: dict[str, float],
        box2: dict[str, float],
        tolerance: float = 1.0
    ) -> bool:
        """
        Check if two bounding boxes are equal within tolerance.
        
        Args:
            box1: First bounding box
            box2: Second bounding box
            tolerance: Tolerance in pixels
            
        Returns:
            True if boxes are equal within tolerance
        """
        for key in ["x", "y", "width", "height"]:
            if abs(box1[key] - box2[key]) > tolerance:
                return False
        return True
