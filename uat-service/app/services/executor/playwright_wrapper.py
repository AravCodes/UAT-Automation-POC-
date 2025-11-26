"""
Playwright wrapper for browser lifecycle management.

This module provides a high-level abstraction over Playwright for managing
browser instances, contexts, and pages. It supports headless and headed modes,
handles browser lifecycle, and provides utilities for test execution.

Requirements: 5.1
"""

import asyncio
from typing import Optional, Literal
from contextlib import asynccontextmanager

from playwright.async_api import (
    async_playwright,
    Playwright,
    Browser,
    BrowserContext,
    Page,
    Error as PlaywrightError
)

from app.core.config import get_config
from app.core.exceptions import BrowserException, ExecutionException
from app.core.logging import get_logger


logger = get_logger(__name__)


BrowserType = Literal["chromium", "firefox", "webkit"]


class PlaywrightWrapper:
    """
    Wrapper for Playwright browser management.
    
    Manages browser lifecycle, contexts, and pages with proper cleanup.
    Supports headless and headed modes with configurable options.
    """
    
    def __init__(
        self,
        browser_type: BrowserType = "chromium",
        headless: Optional[bool] = None,
        slow_mo: Optional[int] = None
    ):
        """
        Initialize the Playwright wrapper.
        
        Args:
            browser_type: Type of browser to use (chromium, firefox, webkit)
            headless: Run browser in headless mode (None = use config default)
            slow_mo: Slow down operations by specified milliseconds (None = use config)
        """
        self.config = get_config()
        self.browser_type = browser_type
        self.headless = headless if headless is not None else self.config.headless_mode
        self.slow_mo = slow_mo if slow_mo is not None else self.config.slow_mo
        
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._contexts: list[BrowserContext] = []
        
        logger.info(
            "playwright_wrapper_initialized",
            extra={
                "browser_type": self.browser_type,
                "headless": self.headless,
                "slow_mo": self.slow_mo
            }
        )
    
    async def start(self) -> None:
        """
        Start Playwright and launch the browser.
        
        Raises:
            BrowserException: If browser fails to start
        """
        try:
            logger.info("starting_playwright")
            
            # Start Playwright
            self._playwright = await async_playwright().start()
            
            # Get browser launcher based on type
            if self.browser_type == "chromium":
                launcher = self._playwright.chromium
            elif self.browser_type == "firefox":
                launcher = self._playwright.firefox
            elif self.browser_type == "webkit":
                launcher = self._playwright.webkit
            else:
                raise BrowserException(
                    f"Unsupported browser type: {self.browser_type}",
                    details={"browser_type": self.browser_type}
                )
            
            # Launch browser with configuration
            self._browser = await launcher.launch(
                headless=self.headless,
                slow_mo=self.slow_mo,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox"
                ] if self.browser_type == "chromium" else None
            )
            
            logger.info(
                "playwright_started",
                extra={
                    "browser_type": self.browser_type,
                    "headless": self.headless
                }
            )
            
        except PlaywrightError as e:
            logger.error(
                "playwright_start_failed",
                extra={"error": str(e)},
                exc_info=True
            )
            raise BrowserException(
                f"Failed to start Playwright browser: {str(e)}",
                browser_type=self.browser_type,
                original_exception=e
            )
        except Exception as e:
            logger.error(
                "unexpected_error_starting_playwright",
                extra={"error": str(e)},
                exc_info=True
            )
            raise BrowserException(
                f"Unexpected error starting Playwright: {str(e)}",
                browser_type=self.browser_type,
                original_exception=e
            )
    
    async def stop(self) -> None:
        """
        Stop the browser and cleanup resources.
        
        Closes all contexts and pages, then closes the browser.
        """
        try:
            logger.info("stopping_playwright")
            
            # Close all contexts
            for context in self._contexts:
                try:
                    await context.close()
                except Exception as e:
                    logger.warning(
                        "context_close_failed",
                        extra={"error": str(e)}
                    )
            
            self._contexts.clear()
            
            # Close browser
            if self._browser:
                await self._browser.close()
                self._browser = None
            
            # Stop Playwright
            if self._playwright:
                await self._playwright.stop()
                self._playwright = None
            
            logger.info("playwright_stopped")
            
        except Exception as e:
            logger.error(
                "error_stopping_playwright",
                extra={"error": str(e)},
                exc_info=True
            )
            # Don't raise exception during cleanup
    
    async def create_context(
        self,
        viewport: Optional[dict] = None,
        user_agent: Optional[str] = None,
        locale: Optional[str] = None,
        timezone: Optional[str] = None,
        permissions: Optional[list[str]] = None,
        record_video: bool = False,
        record_video_dir: Optional[str] = None
    ) -> BrowserContext:
        """
        Create a new browser context.
        
        A browser context is an isolated environment similar to an incognito window.
        Each context has its own cookies, storage, and cache.
        
        Args:
            viewport: Viewport size (e.g., {"width": 1280, "height": 720})
            user_agent: Custom user agent string
            locale: Locale for the context (e.g., "en-US")
            timezone: Timezone ID (e.g., "America/New_York")
            permissions: List of permissions to grant (e.g., ["geolocation"])
            record_video: Whether to record video of the session
            record_video_dir: Directory to save recorded videos
        
        Returns:
            BrowserContext: New browser context
            
        Raises:
            BrowserException: If context creation fails
        """
        if not self._browser:
            raise BrowserException(
                "Browser not started. Call start() first.",
                details={"operation": "create_context"}
            )
        
        try:
            logger.debug("creating_browser_context")
            
            # Default viewport if not specified
            if viewport is None:
                viewport = {"width": 1280, "height": 720}
            
            # Build context options
            context_options = {
                "viewport": viewport,
                "ignore_https_errors": True,
                "java_script_enabled": True
            }
            
            if user_agent:
                context_options["user_agent"] = user_agent
            
            if locale:
                context_options["locale"] = locale
            
            if timezone:
                context_options["timezone_id"] = timezone
            
            if permissions:
                context_options["permissions"] = permissions
            
            if record_video and record_video_dir:
                context_options["record_video_dir"] = record_video_dir
                context_options["record_video_size"] = viewport
            
            # Create context
            context = await self._browser.new_context(**context_options)
            
            # Track context for cleanup
            self._contexts.append(context)
            
            logger.info(
                "browser_context_created",
                extra={
                    "viewport": viewport,
                    "contexts_count": len(self._contexts)
                }
            )
            
            return context
            
        except PlaywrightError as e:
            logger.error(
                "context_creation_failed",
                extra={"error": str(e)},
                exc_info=True
            )
            raise BrowserException(
                f"Failed to create browser context: {str(e)}",
                original_exception=e
            )
    
    async def close_context(self, context: BrowserContext) -> None:
        """
        Close a browser context and remove it from tracking.
        
        Args:
            context: The context to close
        """
        try:
            await context.close()
            
            if context in self._contexts:
                self._contexts.remove(context)
            
            logger.debug(
                "browser_context_closed",
                extra={"contexts_remaining": len(self._contexts)}
            )
            
        except Exception as e:
            logger.warning(
                "context_close_failed",
                extra={"error": str(e)}
            )
    
    @asynccontextmanager
    async def context(
        self,
        **kwargs
    ):
        """
        Context manager for browser context lifecycle.
        
        Usage:
            async with wrapper.context() as context:
                page = await context.new_page()
                # ... use page ...
        
        Args:
            **kwargs: Arguments passed to create_context()
            
        Yields:
            BrowserContext: Browser context that will be automatically closed
        """
        context = await self.create_context(**kwargs)
        try:
            yield context
        finally:
            await self.close_context(context)
    
    @asynccontextmanager
    async def page(
        self,
        context: Optional[BrowserContext] = None,
        **context_kwargs
    ):
        """
        Context manager for page lifecycle.
        
        Usage:
            async with wrapper.page() as page:
                await page.goto("https://example.com")
                # ... use page ...
        
        Args:
            context: Existing context to use (None = create new context)
            **context_kwargs: Arguments for creating new context if needed
            
        Yields:
            Page: Page that will be automatically closed
        """
        # Create context if not provided
        created_context = False
        if context is None:
            context = await self.create_context(**context_kwargs)
            created_context = True
        
        # Create page
        page = await context.new_page()
        
        try:
            yield page
        finally:
            # Close page
            try:
                await page.close()
            except Exception as e:
                logger.warning(
                    "page_close_failed",
                    extra={"error": str(e)}
                )
            
            # Close context if we created it
            if created_context:
                await self.close_context(context)
    
    @property
    def is_started(self) -> bool:
        """Check if browser is started."""
        return self._browser is not None
    
    @property
    def browser(self) -> Browser:
        """
        Get the browser instance.
        
        Returns:
            Browser: The browser instance
            
        Raises:
            BrowserException: If browser is not started
        """
        if not self._browser:
            raise BrowserException(
                "Browser not started. Call start() first.",
                details={"operation": "get_browser"}
            )
        return self._browser
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()


# ============================================================================
# Utility Functions
# ============================================================================

async def create_playwright_wrapper(
    browser_type: BrowserType = "chromium",
    headless: Optional[bool] = None,
    slow_mo: Optional[int] = None
) -> PlaywrightWrapper:
    """
    Create and start a Playwright wrapper.
    
    Args:
        browser_type: Type of browser to use
        headless: Run in headless mode
        slow_mo: Slow down operations (milliseconds)
    
    Returns:
        PlaywrightWrapper: Started wrapper instance
        
    Raises:
        BrowserException: If browser fails to start
    """
    wrapper = PlaywrightWrapper(
        browser_type=browser_type,
        headless=headless,
        slow_mo=slow_mo
    )
    await wrapper.start()
    return wrapper
