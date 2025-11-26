"""
Simple standalone test for token manager (no dependencies).
"""

import asyncio
import time
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))


# Mock the dependencies
class MockConfig:
    rate_limit_per_minute = 60


class MockLogger:
    def info(self, msg, **kwargs):
        pass
    
    def debug(self, msg, **kwargs):
        pass
    
    def warning(self, msg, **kwargs):
        pass
    
    def error(self, msg, **kwargs):
        pass


# Patch the imports
import app.core.config as config_module
import app.core.logging as logging_module

config_module.get_config = lambda: MockConfig()
logging_module.get_logger = lambda name: MockLogger()

# Now import the token manager
from app.services.llm.token_manager import TokenManager, create_token_manager


async def test_basic_token_acquisition():
    """Test basic token acquisition."""
    print("\n=== Test 1: Basic Token Acquisition ===")
    
    # Create manager with low rate limit for testing
    manager = create_token_manager(requests_per_minute=10, burst_size=3)
    
    # Acquire tokens immediately (should be instant)
    print("Acquiring 3 tokens (should be instant)...")
    for i in range(3):
        wait_time = await manager.acquire_token(f"req_{i}")
        print(f"  Request {i}: wait_time={wait_time:.3f}s")
        assert wait_time < 0.1, f"Expected instant, got {wait_time}s"
    
    # Next request should wait
    print("\nAcquiring 4th token (should wait)...")
    wait_time = await manager.acquire_token("req_3")
    print(f"  Request 3: wait_time={wait_time:.3f}s")
    assert wait_time > 0, f"Expected wait, got {wait_time}s"
    
    # Check metrics
    metrics = manager.get_metrics()
    print(f"\nMetrics:")
    print(f"  Total requests: {metrics.total_requests}")
    print(f"  Queued requests: {metrics.queued_requests}")
    print(f"  Average wait time: {metrics.get_average_wait_time():.3f}s")
    print(f"  Max wait time: {metrics.max_wait_time:.3f}s")
    
    assert metrics.total_requests == 4
    assert metrics.queued_requests >= 1
    print("✓ Test passed")


async def test_concurrent_requests():
    """Test concurrent request handling."""
    print("\n=== Test 2: Concurrent Requests ===")
    
    # Create manager with moderate rate limit
    manager = create_token_manager(requests_per_minute=20, burst_size=5)
    
    async def make_request(request_id: str):
        start = time.monotonic()
        wait_time = await manager.acquire_token(request_id)
        duration = time.monotonic() - start
        return wait_time
    
    # Launch 10 concurrent requests
    print("Launching 10 concurrent requests...")
    start = time.monotonic()
    tasks = [make_request(f"req_{i}") for i in range(10)]
    results = await asyncio.gather(*tasks)
    total_duration = time.monotonic() - start
    
    print(f"  Total duration: {total_duration:.3f}s")
    print(f"  First 5 requests (burst): {[f'{r:.3f}s' for r in results[:5]]}")
    print(f"  Next 5 requests (queued): {[f'{r:.3f}s' for r in results[5:]]}")
    
    # Check metrics
    metrics = manager.get_metrics()
    print(f"\nMetrics:")
    print(f"  Total requests: {metrics.total_requests}")
    print(f"  Queued requests: {metrics.queued_requests}")
    print(f"  Average wait time: {metrics.get_average_wait_time():.3f}s")
    
    assert metrics.total_requests == 10
    assert metrics.queued_requests >= 5
    print("✓ Test passed")


async def test_try_acquire():
    """Test non-blocking token acquisition."""
    print("\n=== Test 3: Non-blocking Acquisition ===")
    
    # Create manager with very low rate limit
    manager = create_token_manager(requests_per_minute=6, burst_size=2)
    
    # Acquire all burst tokens
    print("Acquiring burst tokens...")
    for i in range(2):
        acquired = await manager.try_acquire_token(f"req_{i}")
        print(f"  Request {i}: acquired={acquired}")
        assert acquired, f"Expected to acquire token {i}"
    
    # Try to acquire when empty (should fail)
    print("\nTrying to acquire when empty...")
    acquired = await manager.try_acquire_token("req_2")
    print(f"  Request 2: acquired={acquired}")
    assert not acquired, "Expected to fail when empty"
    
    # Wait enough time for at least 1 token to refill
    # 6 requests/min = 0.1 tokens/sec, so need 10 seconds for 1 token
    print("\nWaiting 10 seconds for refill (6 req/min = 0.1 tokens/sec)...")
    await asyncio.sleep(10)
    acquired = await manager.try_acquire_token("req_3")
    print(f"  Request 3: acquired={acquired}")
    assert acquired, "Expected to acquire after refill"
    
    print("✓ Test passed")


async def test_approaching_limit():
    """Test rate limit warning."""
    print("\n=== Test 4: Approaching Limit Detection ===")
    
    manager = create_token_manager(requests_per_minute=12, burst_size=5)
    
    # Check initial state
    available = await manager.get_available_tokens()
    approaching = await manager.is_approaching_limit(threshold=0.5)
    print(f"Initial: available={available:.2f}, approaching_limit={approaching}")
    assert not approaching, "Should not be approaching limit initially"
    
    # Consume some tokens
    print("\nConsuming 3 tokens...")
    for i in range(3):
        await manager.acquire_token(f"req_{i}")
    
    available = await manager.get_available_tokens()
    approaching = await manager.is_approaching_limit(threshold=0.5)
    print(f"After 3 requests: available={available:.2f}, approaching_limit={approaching}")
    assert approaching, "Should be approaching limit after consuming 60%"
    
    print("✓ Test passed")


async def test_refill_rate():
    """Test token refill rate."""
    print("\n=== Test 5: Token Refill Rate ===")
    
    # 60 requests per minute = 1 per second
    manager = create_token_manager(requests_per_minute=60, burst_size=5)
    
    # Consume all tokens
    print("Consuming all 5 burst tokens...")
    for i in range(5):
        await manager.acquire_token(f"req_{i}")
    
    available = await manager.get_available_tokens()
    print(f"After consuming: available={available:.2f}")
    assert available < 0.1, "Should have no tokens left"
    
    # Wait 2 seconds (should refill ~2 tokens)
    print("\nWaiting 2 seconds for refill...")
    await asyncio.sleep(2)
    
    available = await manager.get_available_tokens()
    print(f"After 2 seconds: available={available:.2f}")
    assert 1.5 < available < 2.5, f"Expected ~2 tokens, got {available}"
    
    print("✓ Test passed")


async def main():
    """Run all tests."""
    print("=" * 60)
    print("Token Manager Test Suite")
    print("=" * 60)
    
    try:
        await test_basic_token_acquisition()
        await test_concurrent_requests()
        await test_try_acquire()
        await test_approaching_limit()
        await test_refill_rate()
        
        print("\n" + "=" * 60)
        print("✓ All tests completed successfully!")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n❌ Test assertion failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
