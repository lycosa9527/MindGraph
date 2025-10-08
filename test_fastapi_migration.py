#!/usr/bin/env python3
"""
FastAPI Migration Test Suite
=============================

Comprehensive tests for the migrated FastAPI application.

@author lycosa9527
@made_by MindSpring Team

Usage:
    python test_fastapi_migration.py
"""

import sys
import time
import json
import asyncio
from typing import Dict, Any

def test_imports():
    """Test 1: Verify all critical imports work"""
    print("=" * 80)
    print("TEST 1: Import Verification")
    print("=" * 80)
    
    try:
        # FastAPI app
        from main import app
        print("[OK] main.app imported successfully")
        
        # Async clients
        from async_dify_client import AsyncDifyClient
        print("[OK] AsyncDifyClient imported successfully")
        
        from llm_clients import qwen_client_generation, qwen_client_classification
        print("[OK] LLM clients imported successfully")
        
        # Routers
        from routers import pages, cache, api
        print("[OK] All routers imported successfully")
        
        # Models
        from models import GenerateRequest, GenerateResponse, AIAssistantRequest
        print("[OK] Pydantic models imported successfully")
        
        # Browser manager
        from browser_manager import BrowserContextManager
        print("[OK] BrowserContextManager imported successfully")
        
        print(f"\n[OK] All imports successful!\n")
        return True
        
    except Exception as e:
        print(f"\n[FAIL] Import failed: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def test_app_routes():
    """Test 2: Verify all expected routes are registered"""
    print("=" * 80)
    print("TEST 2: Route Registration")
    print("=" * 80)
    
    try:
        from main import app
        
        routes = [route.path for route in app.routes]
        
        # Expected critical routes
        critical_routes = [
            '/api/ai_assistant/stream',
            '/api/generate_graph',
            '/api/export_png',
            '/api/frontend_log',
            '/',
            '/editor',
            '/health',
            '/status'
        ]
        
        print(f"Total routes registered: {len(routes)}")
        print(f"\nCritical routes check:")
        
        all_found = True
        for route in critical_routes:
            if route in routes:
                print(f"  [OK] {route}")
            else:
                print(f"  [FAIL] {route} - MISSING!")
                all_found = False
        
        if all_found:
            print(f"\n[OK] All critical routes registered!\n")
            return True
        else:
            print(f"\n[FAIL] Some critical routes are missing!\n")
            return False
            
    except Exception as e:
        print(f"\n[FAIL] Route check failed: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def test_no_requests_library():
    """Test 3: Verify NO requests library usage (100% async)"""
    print("=" * 80)
    print("TEST 3: 100% Async Verification (No requests library)")
    print("=" * 80)
    
    import os
    import subprocess
    
    try:
        # Search for "import requests" in production code
        result = subprocess.run(
            ['grep', '-r', 'import requests', 
             '--exclude-dir=venv', '--exclude-dir=.git', 
             '--exclude-dir=__pycache__', '--exclude-dir=test',
             '--exclude=test_*.py', '--exclude=*test*.py',
             '.'],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        
        if result.returncode == 1:  # grep returns 1 when no matches found
            print("[OK] ZERO 'import requests' found in production code!")
            print("[OK] 100% async confirmed!\n")
            return True
        else:
            print(f"[FAIL] Found 'import requests' in production code:")
            print(result.stdout)
            print("\n[FAIL] Not 100% async!\n")
            return False
            
    except FileNotFoundError:
        # grep not available (Windows)
        print("[WARN]  grep not available (Windows), checking manually...")
        
        # Manual check for critical files
        files_to_check = [
            'llm_clients.py',
            'async_dify_client.py',
            'routers/api.py',
            'main.py'
        ]
        
        all_clean = True
        for filepath in files_to_check:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if 'import requests' in content:
                        print(f"  [FAIL] {filepath} - contains 'import requests'")
                        all_clean = False
                    else:
                        print(f"  [OK] {filepath} - clean")
            except Exception as e:
                print(f"  [WARN]  {filepath} - couldn't check: {e}")
        
        if all_clean:
            print("\n[OK] All checked files are clean (no requests library)\n")
            return True
        else:
            print("\n[FAIL] Some files still use requests library!\n")
            return False


async def test_async_dify_client():
    """Test 4: Verify AsyncDifyClient works"""
    print("=" * 80)
    print("TEST 4: AsyncDifyClient Functionality")
    print("=" * 80)
    
    try:
        from async_dify_client import AsyncDifyClient
        
        # Create client instance
        client = AsyncDifyClient(
            api_key="test_key",
            api_url="https://test.api.com",
            timeout=30
        )
        
        print(f"[OK] AsyncDifyClient created successfully")
        print(f"   API URL: {client.api_url}")
        print(f"   Timeout: {client.timeout}s")
        
        # Verify it's an async generator
        import inspect
        if inspect.isasyncgenfunction(client.stream_chat):
            print(f"[OK] stream_chat() is an async generator")
        else:
            print(f"[FAIL] stream_chat() is NOT an async generator")
            return False
        
        print(f"\n[OK] AsyncDifyClient test passed!\n")
        return True
        
    except Exception as e:
        print(f"\n[FAIL] AsyncDifyClient test failed: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def test_pydantic_models():
    """Test 5: Verify Pydantic models validate correctly"""
    print("=" * 80)
    print("TEST 5: Pydantic Model Validation")
    print("=" * 80)
    
    try:
        from models import GenerateRequest, AIAssistantRequest
        from models.common import LLMModel, Language
        
        # Test GenerateRequest
        req1 = GenerateRequest(
            prompt="测试概念图",
            language=Language.ZH,
            llm=LLMModel.QWEN
        )
        print(f"[OK] GenerateRequest created: {req1.prompt[:20]}...")
        
        # Test AIAssistantRequest
        req2 = AIAssistantRequest(
            message="Hello AI",
            user_id="test_user_123"
        )
        print(f"[OK] AIAssistantRequest created: user={req2.user_id}")
        
        # Test validation (should fail with empty prompt)
        try:
            invalid = GenerateRequest(prompt="", language=Language.ZH, llm=LLMModel.QWEN)
            print(f"[FAIL] Validation failed - accepted empty prompt")
            return False
        except Exception:
            print(f"[OK] Validation working - rejected empty prompt")
        
        print(f"\n[OK] Pydantic models test passed!\n")
        return True
        
    except Exception as e:
        print(f"\n[FAIL] Pydantic models test failed: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def test_uvicorn_config():
    """Test 6: Verify Uvicorn configuration is valid"""
    print("=" * 80)
    print("TEST 6: Uvicorn Configuration")
    print("=" * 80)
    
    try:
        # Load uvicorn config
        config_vars = {}
        with open('uvicorn.conf.py', 'r') as f:
            exec(f.read(), config_vars)
        
        print(f"[OK] uvicorn.conf.py loaded successfully")
        print(f"   Host: {config_vars.get('host', 'N/A')}")
        print(f"   Port: {config_vars.get('port', 'N/A')}")
        print(f"   Workers: {config_vars.get('workers', 'N/A')}")
        print(f"   Timeout Keep-Alive: {config_vars.get('timeout_keep_alive', 'N/A')}s")
        
        # Verify critical settings
        assert config_vars.get('timeout_keep_alive') >= 300, "Timeout too short for SSE"
        assert config_vars.get('workers') >= 1, "Need at least 1 worker"
        
        print(f"\n[OK] Uvicorn configuration is valid!\n")
        return True
        
    except Exception as e:
        print(f"\n[FAIL] Uvicorn config test failed: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n")
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 20 + "FASTAPI MIGRATION TEST SUITE" + " " * 30 + "║")
    print("╚" + "═" * 78 + "╝")
    print()
    
    results = {}
    
    # Synchronous tests
    results['imports'] = test_imports()
    results['routes'] = test_app_routes()
    results['no_requests'] = test_no_requests_library()
    results['pydantic'] = test_pydantic_models()
    results['uvicorn_config'] = test_uvicorn_config()
    
    # Async tests
    results['async_dify'] = asyncio.run(test_async_dify_client())
    
    # Summary
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    
    for test_name, result in results.items():
        status = "[OK] PASS" if result else "[FAIL] FAIL"
        print(f"{status} - {test_name}")
    
    print()
    print(f"Total: {passed}/{total} tests passed")
    print("=" * 80)
    
    if passed == total:
        print("\n*** ALL TESTS PASSED! FastAPI migration is ready for deployment! ***\n")
        return 0
    else:
        print(f"\n[WARN]  {total - passed} test(s) failed. Please review and fix.\n")
        return 1


if __name__ == '__main__':
    sys.exit(main())

