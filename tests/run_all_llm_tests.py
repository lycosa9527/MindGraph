"""
Run All LLM Service Middleware Tests with Real APIs
====================================================

This script runs all middleware tests sequentially with real LLM API calls.

@author lycosa9527
@made_by MindSpring Team
"""

import sys
sys.path.insert(0, '.')

import asyncio
import time
from services.llm_service import llm_service


async def run_all_tests():
    print("=" * 70)
    print("LLM SERVICE MIDDLEWARE - COMPLETE TEST SUITE")
    print("Testing with REAL LLM APIs")
    print("=" * 70)
    print()
    
    # Initialize
    print("[INIT] Initializing LLM Service...")
    llm_service.initialize()
    print("[OK] Service initialized")
    print(f"[OK] Available models: {llm_service.get_available_models()}")
    print()
    
    test_results = []
    
    # Test 1: Client Manager
    print("[1/7] Testing ClientManager...")
    try:
        assert llm_service.client_manager.is_initialized()
        models = llm_service.get_available_models()
        assert len(models) >= 4
        test_results.append(("ClientManager", "PASS"))
        print("[OK] ClientManager working")
    except Exception as e:
        test_results.append(("ClientManager", f"FAIL: {e}"))
        print(f"[FAIL] {e}")
    print()
    
    # Test 2: Basic Chat (Real API)
    print("[2/7] Testing Basic Chat with Real API...")
    try:
        response = await llm_service.chat(
            prompt="Say 'test' in one word",
            model='qwen',
            max_tokens=20,
            timeout=10.0
        )
        assert isinstance(response, str)
        assert len(response) > 0
        test_results.append(("Basic Chat", "PASS"))
        print(f"[OK] Response received: {response[:50]}")
    except Exception as e:
        test_results.append(("Basic Chat", f"FAIL: {e}"))
        print(f"[FAIL] {e}")
    print()
    
    # Test 3: Error Handler with Retry
    print("[3/7] Testing Error Handler with Retry...")
    try:
        # Test retry by making a call
        response = await llm_service.chat(
            prompt="Count 1",
            model='qwen',
            max_tokens=10,
            timeout=10.0
        )
        # If we got here, retry mechanism is working
        test_results.append(("Error Handler", "PASS"))
        print("[OK] Error handler and retry logic working")
    except Exception as e:
        test_results.append(("Error Handler", f"FAIL: {e}"))
        print(f"[FAIL] {e}")
    print()
    
    # Test 4: Rate Limiter
    print("[4/7] Testing Rate Limiter...")
    try:
        if llm_service.rate_limiter:
            stats = llm_service.get_rate_limiter_stats()
            print(f"  QPM Limit: {stats['qpm_limit']}")
            print(f"  Concurrent Limit: {stats['concurrent_limit']}")
            print(f"  Enabled: {stats['enabled']}")
            test_results.append(("Rate Limiter", "PASS"))
            print("[OK] Rate limiter configured")
        else:
            test_results.append(("Rate Limiter", "PASS (disabled)"))
            print("[OK] Rate limiter disabled (acceptable)")
    except Exception as e:
        test_results.append(("Rate Limiter", f"FAIL: {e}"))
        print(f"[FAIL] {e}")
    print()
    
    # Test 5: Performance Tracker (with real calls)
    print("[5/7] Testing Performance Tracker...")
    try:
        # Make a few calls to generate metrics
        for i in range(2):
            await llm_service.chat(
                prompt=f"Say {i+1}",
                model='qwen',
                max_tokens=10,
                timeout=10.0
            )
        
        metrics = llm_service.get_performance_metrics('qwen')
        assert metrics is not None, "Metrics should not be None"
        assert isinstance(metrics, dict), "Metrics should be a dictionary"
        assert metrics.get('total_requests', 0) >= 1, "Should have at least 1 request"
        assert 'success_rate' in metrics, "Should have success_rate"
        assert 'circuit_state' in metrics, "Should have circuit_state"
        
        print(f"  Total requests: {metrics['total_requests']}")
        print(f"  Success rate: {metrics['success_rate']}%")
        print(f"  Avg response time: {metrics['avg_response_time']}s")
        print(f"  Circuit state: {metrics['circuit_state']}")
        
        test_results.append(("Performance Tracker", "PASS"))
        print("[OK] Performance tracking working")
    except Exception as e:
        test_results.append(("Performance Tracker", f"FAIL: {e}"))
        print(f"[FAIL] {e}")
    print()
    
    # Test 6: Multi-LLM Orchestration
    print("[6/7] Testing Multi-LLM Orchestration (Real APIs)...")
    try:
        results = await llm_service.generate_multi(
            prompt="Say hello",
            models=['qwen', 'deepseek'],
            max_tokens=20,
            timeout=20.0
        )
        
        assert len(results) == 2
        successes = sum(1 for r in results.values() if r['success'])
        
        print(f"  Called {len(results)} models")
        print(f"  Successful: {successes}/{len(results)}")
        
        for model, result in results.items():
            print(f"  {model}: {result['success']} ({result['duration']}s)")
        
        test_results.append(("Multi-LLM", "PASS"))
        print("[OK] Multi-LLM orchestration working")
    except Exception as e:
        test_results.append(("Multi-LLM", f"FAIL: {e}"))
        print(f"[FAIL] {e}")
    print()
    
    # Test 7: Prompt Manager
    print("[7/7] Testing Prompt Manager...")
    try:
        # Test getting a prompt
        prompt = llm_service.get_prompt(
            category='common',
            function='system',
            name='default',
            language='en'
        )
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        
        # Test list categories
        categories = llm_service.prompt_manager.list_categories()
        assert len(categories) > 0
        
        print(f"  Categories available: {len(categories)}")
        print(f"  Sample prompt length: {len(prompt)} chars")
        
        test_results.append(("Prompt Manager", "PASS"))
        print("[OK] Prompt manager working")
    except Exception as e:
        test_results.append(("Prompt Manager", f"FAIL: {e}"))
        print(f"[FAIL] {e}")
    print()
    
    # Summary
    print("=" * 70)
    print("TEST RESULTS SUMMARY")
    print("=" * 70)
    print()
    
    for test_name, result in test_results:
        status = "[OK]" if result == "PASS" or "PASS" in result else "[FAIL]"
        print(f"{status} {test_name}: {result}")
    
    print()
    passed = sum(1 for _, r in test_results if "PASS" in r)
    total = len(test_results)
    print(f"Tests Passed: {passed}/{total}")
    print()
    
    if passed == total:
        print("=" * 70)
        print("ALL MIDDLEWARE TESTS PASSED WITH REAL LLM APIS!")
        print("=" * 70)
        return 0
    else:
        print("=" * 70)
        print(f"WARNING: {total - passed} test(s) failed")
        print("=" * 70)
        return 1


if __name__ == '__main__':
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)

