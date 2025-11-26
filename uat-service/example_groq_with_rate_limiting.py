"""
Example: Integrating TokenManager with GroqClient

This example demonstrates how to use the TokenManager with the GroqClient
to implement rate limiting and request queuing.

Requirements: 1.7
"""

import asyncio
from app.services.llm.groq_client import GroqClient
from app.services.llm.token_manager import get_token_manager


async def example_with_rate_limiting():
    """
    Example of using GroqClient with TokenManager for rate limiting.
    
    The TokenManager ensures that requests are queued when approaching
    rate limits, preventing API errors and ensuring smooth operation.
    """
    
    # Get the global token manager instance
    token_manager = get_token_manager()
    
    # Create Groq client
    async with GroqClient() as client:
        
        # Example: Parse multiple user stories with rate limiting
        stories = [
            "As a user, I want to login with email and password",
            "As an admin, I want to manage user accounts",
            "As a user, I want to view my profile",
            "As a user, I want to update my settings",
            "As an admin, I want to generate reports",
        ]
        
        print("Processing user stories with rate limiting...\n")
        
        for i, story in enumerate(stories):
            # Acquire token before making request
            # This will queue the request if rate limit is approached
            request_id = f"story_{i}"
            wait_time = await token_manager.acquire_token(request_id)
            
            if wait_time > 0:
                print(f"[{request_id}] Waited {wait_time:.2f}s due to rate limiting")
            
            # Check if we're approaching the rate limit
            if await token_manager.is_approaching_limit(threshold=0.3):
                print(f"[{request_id}] ⚠️  Approaching rate limit")
            
            # Make the actual API request
            try:
                result = await client.parse_story(
                    story_text=story,
                    prompt_template="Parse this user story: {story_text}",
                )
                print(f"[{request_id}] ✓ Parsed: {story[:50]}...")
                
            except Exception as e:
                print(f"[{request_id}] ✗ Error: {e}")
        
        # Print metrics
        print("\n" + "=" * 60)
        print("Rate Limiting Metrics:")
        print("=" * 60)
        
        metrics = token_manager.get_metrics()
        print(f"Total requests: {metrics.total_requests}")
        print(f"Queued requests: {metrics.queued_requests}")
        print(f"Average wait time: {metrics.get_average_wait_time():.2f}s")
        print(f"Max wait time: {metrics.max_wait_time:.2f}s")
        print(f"Rate limit hits: {metrics.rate_limit_hits}")
        
        queue_size = await token_manager.get_queue_size()
        available_tokens = await token_manager.get_available_tokens()
        print(f"\nCurrent queue size: {queue_size}")
        print(f"Available tokens: {available_tokens:.2f}")


async def example_concurrent_with_rate_limiting():
    """
    Example of concurrent requests with rate limiting.
    
    This shows how the TokenManager handles multiple concurrent requests,
    queuing them as needed to respect rate limits.
    """
    
    token_manager = get_token_manager()
    
    async def process_story(story_id: int, story_text: str):
        """Process a single story with rate limiting."""
        request_id = f"concurrent_{story_id}"
        
        # Acquire token (will queue if needed)
        wait_time = await token_manager.acquire_token(request_id)
        
        # Simulate API call
        await asyncio.sleep(0.1)
        
        return {
            "id": story_id,
            "wait_time": wait_time,
            "story": story_text[:30] + "...",
        }
    
    # Launch many concurrent requests
    stories = [f"Story {i}: As a user, I want feature {i}" for i in range(20)]
    
    print("\nProcessing 20 concurrent requests with rate limiting...\n")
    
    tasks = [process_story(i, story) for i, story in enumerate(stories)]
    results = await asyncio.gather(*tasks)
    
    # Analyze results
    queued_count = sum(1 for r in results if r["wait_time"] > 0)
    total_wait = sum(r["wait_time"] for r in results)
    
    print(f"Completed {len(results)} requests")
    print(f"Queued requests: {queued_count}")
    print(f"Total wait time: {total_wait:.2f}s")
    print(f"Average wait: {total_wait / len(results):.2f}s")


async def example_check_before_batch():
    """
    Example of checking rate limit status before batch operations.
    
    This shows how to check if you're approaching the rate limit
    before starting a large batch of requests.
    """
    
    token_manager = get_token_manager()
    
    # Check current status
    available = await token_manager.get_available_tokens()
    approaching = await token_manager.is_approaching_limit(threshold=0.5)
    wait_time = await token_manager.get_estimated_wait_time()
    
    print("\nRate Limit Status Check:")
    print(f"  Available tokens: {available:.2f}")
    print(f"  Approaching limit: {approaching}")
    print(f"  Estimated wait for next request: {wait_time:.2f}s")
    
    if approaching:
        print("\n⚠️  Rate limit is low. Consider:")
        print("  - Waiting for tokens to refill")
        print("  - Reducing batch size")
        print("  - Using try_acquire_token() for non-critical requests")
        
        # Wait for capacity before proceeding
        print("\nWaiting for capacity...")
        await token_manager.wait_for_capacity(min_tokens=3.0)
        print("✓ Capacity available, proceeding with batch")


async def main():
    """Run all examples."""
    print("=" * 60)
    print("TokenManager Integration Examples")
    print("=" * 60)
    
    try:
        # Note: These examples require a valid GROQ_API_KEY
        # For demonstration, we'll just show the rate limiting logic
        
        print("\n1. Sequential requests with rate limiting")
        print("-" * 60)
        # await example_with_rate_limiting()
        print("(Skipped - requires GROQ_API_KEY)")
        
        print("\n2. Concurrent requests with rate limiting")
        print("-" * 60)
        await example_concurrent_with_rate_limiting()
        
        print("\n3. Check rate limit before batch")
        print("-" * 60)
        await example_check_before_batch()
        
        print("\n" + "=" * 60)
        print("Examples completed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
