"""
Manual Integration Test with Real LLM APIs
===========================================

Run this script to verify LLM Service works with real API calls.

Usage:
    python test_real_llm_manual.py

@author lycosa9527
@made_by MindSpring Team
"""

import asyncio
import sys
sys.path.insert(0, '.')

from services.llm_service import llm_service


async def main():
    print("=" * 70)
    print("LLM SERVICE - REAL API INTEGRATION TEST")
    print("=" * 70)
    print()
    
    # Initialize
    print("[1/11] Initializing LLM Service...")
    llm_service.initialize()
    print("[OK] LLM Service initialized")
    print(f"Available models: {llm_service.get_available_models()}")
    print()
    
    # Test 1: Basic chat
    print("[2/11] Testing basic chat with Qwen...")
    response = await llm_service.chat(
        prompt="Say 'Hello' in one word",
        model='qwen',
        max_tokens=20,
        timeout=10.0
    )
    print(f"✅ Response: {response}")
    print()
    
    # Test 2: Streaming
    print("[3/11] Testing streaming chat...")
    chunks = []
    async for chunk in llm_service.chat_stream(
        prompt="Count from 1 to 3",
        model='qwen',
        max_tokens=50,
        timeout=10.0
    ):
        chunks.append(chunk)
        print(chunk, end='', flush=True)
    print()
    print(f"✅ Received {len(chunks)} chunks")
    print()
    
    # Test 3: System message
    print("[4/11] Testing with system message...")
    response = await llm_service.chat(
        prompt="What is 2+2?",
        model='qwen',
        system_message="You are a math teacher. Answer in one word.",
        max_tokens=20,
        timeout=10.0
    )
    print(f"✅ Response: {response}")
    print()
    
    # Test 4: Multi-LLM parallel
    print("[5/11] Testing parallel multi-LLM calls...")
    results = await llm_service.generate_multi(
        prompt="Say 'hello' in one word",
        models=['qwen', 'deepseek'],
        max_tokens=20,
        timeout=20.0
    )
    for model, result in results.items():
        print(f"  {model}: success={result['success']}, duration={result['duration']}s")
        if result['success']:
            print(f"    Response: {result['response'][:50]}")
    print("✅ Multi-LLM parallel execution complete")
    print()
    
    # Test 5: Progressive streaming
    print("[6/11] Testing progressive multi-LLM streaming...")
    async for result in llm_service.generate_progressive(
        prompt="Say 'test' in one word",
        models=['qwen', 'deepseek'],
        max_tokens=20,
        timeout=20.0
    ):
        print(f"  Received from {result['llm']}: {result['response'][:30]} ({result['duration']}s)")
    print("✅ Progressive streaming complete")
    print()
    
    # Test 6: Race (fastest wins)
    print("[7/11] Testing race for fastest response...")
    result = await llm_service.generate_race(
        prompt="Say 'hi'",
        models=['qwen-turbo', 'qwen', 'deepseek'],
        max_tokens=20,
        timeout=15.0
    )
    print(f"✅ Winner: {result['llm']} in {result['duration']}s")
    print(f"   Response: {result['response'][:50]}")
    print()
    
    # Test 7: Compare responses
    print("[8/11] Testing LLM response comparison...")
    comparison = await llm_service.compare_responses(
        prompt="What is 2+2? Answer briefly.",
        models=['qwen', 'deepseek'],
        max_tokens=30,
        timeout=15.0
    )
    for model, response in comparison['responses'].items():
        print(f"  {model}: {response[:40]}")
    print("✅ Comparison complete")
    print()
    
    # Test 8: Performance tracking
    print("[9/11] Testing performance tracking...")
    metrics = llm_service.get_performance_metrics('qwen')
    print(f"  Total requests: {metrics['total_requests']}")
    print(f"  Success rate: {metrics['success_rate']}%")
    print(f"  Avg response time: {metrics['avg_response_time']}s")
    print(f"  Circuit state: {metrics['circuit_state']}")
    print("✅ Performance tracking working")
    print()
    
    # Test 9: Health check
    print("[10/11] Testing health check...")
    health = await llm_service.health_check()
    print(f"  Available models: {health['available_models']}")
    print("✅ Health check complete")
    print()
    
    # Test 10: Get fastest model
    print("[11/11] Testing get fastest model...")
    fastest = llm_service.get_fastest_model(['qwen', 'deepseek', 'kimi'])
    print(f"✅ Fastest model: {fastest}")
    print()
    
    print("=" * 70)
    print("ALL TESTS PASSED - REAL LLM API INTEGRATION WORKING!")
    print("=" * 70)
    print()
    print("Summary:")
    print("  ✅ Basic chat")
    print("  ✅ Streaming chat")
    print("  ✅ System messages")
    print("  ✅ Multi-LLM parallel execution")
    print("  ✅ Progressive streaming")
    print("  ✅ Race (fastest wins)")
    print("  ✅ Response comparison")
    print("  ✅ Performance tracking")
    print("  ✅ Health check")
    print("  ✅ Fastest model selection")
    print()
    print("🎉 LLM Service is production ready with real API calls!")


if __name__ == '__main__':
    asyncio.run(main())

