"""
Comprehensive Endpoint Test Script
===================================

Tests all API endpoints in the MindGraph application.

Usage:
    python tests/test_all_endpoints.py
    python tests/test_all_endpoints.py --base-url http://localhost:9527
    python tests/test_all_endpoints.py --json

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import asyncio
import sys
import json
import argparse
import os
from typing import Dict, Any, List, Optional
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
        else:
            os.environ['PYTHONIOENCODING'] = 'utf-8'
    except:
        pass

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    import aiohttp
except ImportError:
    print("ERROR: aiohttp not installed. Install with: pip install aiohttp")
    sys.exit(1)


class EndpointTester:
    """Test all endpoints in the MindGraph application."""
    
    def __init__(self, base_url: str = "http://localhost:9527"):
        self.base_url = base_url.rstrip('/')
        self.results = {}
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=60),
            connector=aiohttp.TCPConnector(limit=100)
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def test_endpoint(
        self,
        method: str,
        path: str,
        name: str,
        data: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        expected_status: Optional[int] = None,
        skip_auth: bool = False
    ) -> Dict[str, Any]:
        """Test a single endpoint."""
        import time
        start_time = time.time()
        
        url = f"{self.base_url}{path}"
        
        try:
            if method.upper() == 'GET':
                async with self.session.get(url, headers=headers) as response:
                    return await self._process_response(
                        response, name, url, start_time, expected_status
                    )
            elif method.upper() == 'POST':
                async with self.session.post(url, json=data, headers=headers) as response:
                    return await self._process_response(
                        response, name, url, start_time, expected_status
                    )
            elif method.upper() == 'PUT':
                async with self.session.put(url, json=data, headers=headers) as response:
                    return await self._process_response(
                        response, name, url, start_time, expected_status
                    )
            elif method.upper() == 'DELETE':
                async with self.session.delete(url, headers=headers) as response:
                    return await self._process_response(
                        response, name, url, start_time, expected_status
                    )
            else:
                return {
                    'name': name,
                    'url': url,
                    'method': method,
                    'success': False,
                    'error': f"Unsupported method: {method}",
                    'duration': round(time.time() - start_time, 3)
                }
        except aiohttp.ClientError as e:
            elapsed = time.time() - start_time
            return {
                'name': name,
                'url': url,
                'method': method,
                'success': False,
                'error': f"Connection error: {str(e)}",
                'duration': round(elapsed, 3)
            }
        except Exception as e:
            elapsed = time.time() - start_time
            return {
                'name': name,
                'url': url,
                'method': method,
                'success': False,
                'error': f"Unexpected error: {str(e)}",
                'duration': round(elapsed, 3)
            }
    
    async def _process_response(
        self,
        response: aiohttp.ClientResponse,
        name: str,
        url: str,
        start_time: float,
        expected_status: Optional[int]
    ) -> Dict[str, Any]:
        """Process HTTP response."""
        import time
        elapsed = time.time() - start_time
        
        try:
            # Try to parse as JSON
            try:
                data = await response.json()
            except:
                # If not JSON, get text
                text = await response.text()
                data = {"raw": text[:500]}  # Limit text length
            
            # Check success based on expected status
            if isinstance(expected_status, list):
                success = response.status in expected_status or response.status < 400
            elif expected_status is not None:
                success = response.status == expected_status
            else:
                success = response.status < 400
            
            return {
                'name': name,
                'url': url,
                'method': response.method,
                'http_status': response.status,
                'data': data,
                'success': success,
                'duration': round(elapsed, 3),
                'expected_status': expected_status
            }
        except Exception as e:
            return {
                'name': name,
                'url': url,
                'method': response.method,
                'http_status': response.status,
                'success': False,
                'error': f"Failed to process response: {str(e)}",
                'duration': round(elapsed, 3)
            }
    
    def get_all_endpoints(self) -> List[Dict[str, Any]]:
        """Get list of all endpoints to test."""
        endpoints = []
        
        # Health & Status endpoints (public)
        endpoints.extend([
            {'method': 'GET', 'path': '/health', 'name': 'Health Check', 'skip_auth': True},
            {'method': 'GET', 'path': '/status', 'name': 'Application Status', 'skip_auth': True},
            {'method': 'GET', 'path': '/health/database', 'name': 'Database Health', 'skip_auth': True},
        ])
        
        # Pages (public, but may redirect)
        endpoints.extend([
            {'method': 'GET', 'path': '/', 'name': 'Root Page', 'skip_auth': True, 'expected_status': [200, 303, 307]},
            {'method': 'GET', 'path': '/auth', 'name': 'Auth Page', 'skip_auth': True, 'expected_status': [200, 303]},
            {'method': 'GET', 'path': '/demo', 'name': 'Demo Page', 'skip_auth': True, 'expected_status': [200, 303]},
            {'method': 'GET', 'path': '/favicon.ico', 'name': 'Favicon', 'skip_auth': True, 'expected_status': [200, 404]},
        ])
        
        # API endpoints (may require auth)
        endpoints.extend([
            {'method': 'GET', 'path': '/api/llm/health', 'name': 'LLM Health', 'skip_auth': True},
            {'method': 'GET', 'path': '/api/llm/metrics', 'name': 'LLM Metrics', 'skip_auth': True},
            {'method': 'GET', 'path': '/cache/status', 'name': 'Cache Status', 'skip_auth': False},
            {'method': 'GET', 'path': '/cache/performance', 'name': 'Cache Performance', 'skip_auth': False},
            {'method': 'GET', 'path': '/cache/modular', 'name': 'Cache Modular', 'skip_auth': False},
        ])
        
        # Auth endpoints (public)
        endpoints.extend([
            {'method': 'GET', 'path': '/api/auth/mode', 'name': 'Auth Mode', 'skip_auth': True},
            {'method': 'GET', 'path': '/api/auth/organizations', 'name': 'List Organizations', 'skip_auth': True},
            {'method': 'GET', 'path': '/api/auth/me', 'name': 'Get Current User', 'skip_auth': False},
        ])
        
        # Update notification endpoints
        endpoints.extend([
            {'method': 'GET', 'path': '/api/update-notification', 'name': 'Get Update Notification', 'skip_auth': False},
        ])
        
        # Tab mode endpoints
        endpoints.extend([
            {
                'method': 'POST',
                'path': '/api/tab_suggestions',
                'name': 'Tab Suggestions',
                'data': {
                    'diagram_type': 'mindmap',
                    'main_topics': ['Test'],
                    'partial_input': 'test',
                    'language': 'en'
                },
                'skip_auth': False
            },
            {
                'method': 'POST',
                'path': '/api/tab_expand',
                'name': 'Tab Expand',
                'data': {
                    'diagram_type': 'mindmap',
                    'node_text': 'Test',
                    'main_topic': 'Test',
                    'language': 'en'
                },
                'skip_auth': False
            },
        ])
        
        # Node palette endpoints
        endpoints.extend([
            {
                'method': 'POST',
                'path': '/thinking_mode/node_palette/start',
                'name': 'Node Palette Start',
                'data': {
                    'session_id': 'test_session',
                    'diagram_type': 'circle_map',
                    'diagram_data': {'center': {'text': 'Test'}},
                    'educational_context': ''
                },
                'skip_auth': False
            },
        ])
        
        # API generation endpoints (may require auth)
        endpoints.extend([
            {
                'method': 'POST',
                'path': '/api/generate_graph',
                'name': 'Generate Graph',
                'data': {
                    'prompt': 'Test diagram',
                    'language': 'en'
                },
                'skip_auth': False
            },
            {
                'method': 'POST',
                'path': '/api/generate_png',
                'name': 'Generate PNG',
                'data': {
                    'prompt': 'Test diagram',
                    'language': 'en'
                },
                'skip_auth': False
            },
        ])
        
        # Frontend logging (public)
        endpoints.extend([
            {
                'method': 'POST',
                'path': '/api/frontend_log',
                'name': 'Frontend Log',
                'data': {'level': 'info', 'message': 'Test log'},
                'skip_auth': True
            },
            {
                'method': 'POST',
                'path': '/api/frontend_log_batch',
                'name': 'Frontend Log Batch',
                'data': {
                    'logs': [{'level': 'info', 'message': 'Test'}],
                    'batch_size': 1
                },
                'skip_auth': True
            },
        ])
        
        return endpoints
    
    async def test_all(self, json_output: bool = False) -> Dict[str, Any]:
        """Test all endpoints."""
        import time
        
        endpoints = self.get_all_endpoints()
        
        if not json_output:
            print(f"\n{'='*80}")
            print(f"Testing All MindGraph Endpoints")
            print(f"{'='*80}")
            print(f"Base URL: {self.base_url}")
            print(f"Total Endpoints: {len(endpoints)}")
            print(f"{'='*80}\n")
        
        results = {
            'base_url': self.base_url,
            'total_endpoints': len(endpoints),
            'endpoints': {},
            'summary': {
                'total': len(endpoints),
                'success': 0,
                'failed': 0,
                'skipped': 0
            }
        }
        
        overall_start = time.time()
        
        # Test endpoints sequentially (some may depend on auth state)
        for endpoint in endpoints:
            name = endpoint['name']
            
            # Skip auth-required endpoints if we don't have auth
            if not endpoint.get('skip_auth', False):
                # For now, test them anyway to see what happens
                pass
            
            result = await self.test_endpoint(
                method=endpoint['method'],
                path=endpoint['path'],
                name=name,
                data=endpoint.get('data'),
                headers=endpoint.get('headers'),
                expected_status=endpoint.get('expected_status'),
                skip_auth=endpoint.get('skip_auth', False)
            )
            
            results['endpoints'][name] = result
            
            # Update summary
            if result.get('success'):
                results['summary']['success'] += 1
            elif result.get('http_status') in [401, 403]:
                results['summary']['skipped'] += 1
            else:
                results['summary']['failed'] += 1
            
            # Print progress
            if not json_output:
                status_icon = "✓" if result.get('success') else "✗"
                status_code = result.get('http_status', 'N/A')
                duration = result.get('duration', 0)
                print(f"{status_icon} [{status_code}] {name:40s} ({duration:.3f}s)")
                if result.get('error'):
                    print(f"    Error: {result['error']}")
        
        overall_duration = time.time() - overall_start
        results['_total_duration'] = round(overall_duration, 3)
        
        if not json_output:
            print(f"\n{'='*80}")
            print(f"Summary")
            print(f"{'='*80}")
            print(f"Total: {results['summary']['total']}")
            print(f"Success: {results['summary']['success']}")
            print(f"Failed: {results['summary']['failed']}")
            print(f"Skipped (Auth Required): {results['summary']['skipped']}")
            print(f"Total Duration: {results['_total_duration']:.3f}s")
            print(f"{'='*80}\n")
        
        return results


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Test all MindGraph endpoints')
    parser.add_argument(
        '--base-url',
        default='http://localhost:9527',
        help='Base URL of the MindGraph server (default: http://localhost:9527)'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output results as JSON'
    )
    
    args = parser.parse_args()
    
    async with EndpointTester(base_url=args.base_url) as tester:
        results = await tester.test_all(json_output=args.json)
        
        if args.json:
            print(json.dumps(results, indent=2, ensure_ascii=False))
        else:
            # Print detailed results for failed endpoints
            failed = [
                (name, result)
                for name, result in results['endpoints'].items()
                if not result.get('success') and result.get('http_status') not in [401, 403]
            ]
            
            if failed:
                print(f"\nFailed Endpoints ({len(failed)}):")
                print("="*80)
                for name, result in failed:
                    print(f"\n{name}:")
                    print(f"  URL: {result.get('url')}")
                    print(f"  Status: {result.get('http_status')}")
                    print(f"  Error: {result.get('error', 'Unknown error')}")
                    if result.get('data'):
                        data_preview = str(result['data'])[:200]
                        print(f"  Response: {data_preview}...")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nFatal error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

