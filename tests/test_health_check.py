"""
Comprehensive Health Check Test Script
=======================================

Standalone script to test all health check endpoints including:
- Basic application health (/health)
- Application status with metrics (/status)
- LLM services health (/api/llm/health)
- Database health (/health/database)

Can be run directly without pytest.

Usage:
    python tests/test_health_check.py
    python tests/test_health_check.py --endpoint http://localhost:9527
    python tests/test_health_check.py --direct  # Test service directly instead of HTTP
    python tests/test_health_check.py --json    # Output as JSON
"""

import asyncio
import sys
import json
import argparse
import os
from typing import Dict, Any
from pathlib import Path

# Fix Windows console encoding for Unicode characters
if sys.platform == 'win32':
    try:
        # Try to set UTF-8 encoding
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
        else:
            # Fallback: use ASCII-safe characters
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


async def test_endpoint(session: aiohttp.ClientSession, url: str, name: str) -> Dict[str, Any]:
    """
    Test a single health check endpoint.
    
    Args:
        session: aiohttp session
        url: Endpoint URL
        name: Endpoint name for display
        
    Returns:
        Health check results dictionary with timing information
    """
    import time
    start_time = time.time()
    
    try:
        async with session.get(url) as response:
            try:
                data = await response.json()
            except:
                data = {"raw": await response.text()}
            
            elapsed = time.time() - start_time
            
            return {
                'name': name,
                'url': url,
                'http_status': response.status,
                'data': data,
                'success': True,
                'duration': round(elapsed, 3)
            }
    except aiohttp.ClientError as e:
        elapsed = time.time() - start_time
        return {
            'name': name,
            'url': url,
            'success': False,
            'error': f"Connection error: {str(e)}",
            'duration': round(elapsed, 3)
        }
    except Exception as e:
        elapsed = time.time() - start_time
        return {
            'name': name,
            'url': url,
            'success': False,
            'error': f"Unexpected error: {str(e)}",
            'duration': round(elapsed, 3)
        }


async def test_all_health_endpoints(base_url: str = "http://localhost:9527") -> Dict[str, Any]:
    """
    Test all health check endpoints.
    
    Args:
        base_url: Base URL of the MindGraph server
        
    Returns:
        Dictionary with results from all endpoints including timing
    """
    import time
    
    endpoints = [
        ('/health', 'Basic Health'),
        ('/status', 'Application Status'),
        ('/api/llm/health', 'LLM Services Health'),
        ('/health/database', 'Database Health')
    ]
    
    print(f"\n{'='*60}")
    print(f"Testing All Health Check Endpoints")
    print(f"{'='*60}")
    print(f"Base URL: {base_url}")
    print(f"{'='*60}\n")
    
    results = {}
    overall_start = time.time()
    
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
            # Test all endpoints in parallel
            tasks = [
                test_endpoint(session, f"{base_url}{path}", name)
                for path, name in endpoints
            ]
            
            endpoint_results = await asyncio.gather(*tasks)
            
            for result in endpoint_results:
                results[result['name']] = result
        
        overall_duration = time.time() - overall_start
        results['_total_duration'] = round(overall_duration, 3)
                
    except Exception as e:
        return {
            'error': f"Failed to test endpoints: {str(e)}"
        }
    
    return results


async def test_health_via_http(base_url: str = "http://localhost:9527") -> Dict[str, Any]:
    """
    Test LLM health check via HTTP API endpoint (legacy function for compatibility).
    
    Args:
        base_url: Base URL of the MindGraph server
        
    Returns:
        Health check results dictionary
    """
    url = f"{base_url}/api/llm/health"
    
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            async with session.get(url) as response:
                data = await response.json()
                
                result = {
                    'http_status': response.status,
                    'data': data
                }
                
                return result
    except aiohttp.ClientError as e:
        return {
            'error': f"Connection error: {str(e)}",
            'suggestion': 'Make sure the server is running on the specified URL'
        }
    except Exception as e:
        return {
            'error': f"Unexpected error: {str(e)}"
        }


async def test_health_direct() -> Dict[str, Any]:
    """
    Test health check by calling the service directly.
    
    Returns:
        Health check results dictionary
    """
    print(f"\n{'='*60}")
    print(f"Testing Health Check Directly (Service Layer)")
    print(f"{'='*60}\n")
    
    try:
        from services.llm_service import llm_service
        
        # Initialize if not already initialized
        if not llm_service.client_manager.is_initialized():
            print("Initializing LLM service...")
            llm_service.initialize()
        
        # Run health check
        results = await llm_service.health_check()
        return results
        
    except Exception as e:
        return {
            'error': f"Service error: {str(e)}",
            'type': type(e).__name__
        }


def _get_icons():
    """Get icons, with fallback for Windows console encoding issues."""
    try:
        # Test if we can encode Unicode
        test_char = "✅"
        test_char.encode(sys.stdout.encoding or 'utf-8')
        # Unicode works
        return {
            'check': "✅",
            'cross': "❌",
            'warning': "⚠️",
            'info': "💡",
            'clock': "🕐",
            'chart': "📊",
            'list': "📋",
            'plug': "🔌",
            'green': "🟢",
            'red': "🔴",
            'yellow': "🟡",
            'party': "🎉"
        }
    except (UnicodeEncodeError, AttributeError):
        # Fallback to ASCII
        return {
            'check': "[OK]",
            'cross': "[X]",
            'warning': "[!]",
            'info': "[i]",
            'clock': "[*]",
            'chart': "[*]",
            'list': "[*]",
            'plug': "[*]",
            'green': "[G]",
            'red': "[R]",
            'yellow': "[Y]",
            'party': "[*]"
        }


def format_database_health(results: Dict[str, Any]) -> str:
    """Format database health check results."""
    icons = _get_icons()
    output = []
    
    if 'http_status' in results:
        http_status = results['http_status']
        data = results.get('data', results)
        
        if http_status == 200:
            output.append(f"{icons['check']} HTTP Status: 200 OK (Database healthy)\n")
        elif http_status == 503:
            output.append(f"{icons['warning']} HTTP Status: 503 Service Unavailable (Database unhealthy)\n")
        elif http_status == 500:
            output.append(f"{icons['cross']} HTTP Status: 500 Internal Server Error\n")
        else:
            output.append(f"{icons['cross']} HTTP Status: {http_status} (Unexpected)\n")
        
        results = data
    
    if 'error' in results:
        output.append(f"{icons['cross']} ERROR: {results['error']}")
        return "\n".join(output)
    
    output.append(f"{icons['check']} Database Health Check\n")
    
    if 'status' in results:
        status = results.get('status', 'unknown')
        db_healthy = results.get('database_healthy', False)
        message = results.get('database_message', 'Unknown')
        
        status_icon = icons['check'] if db_healthy else icons['cross']
        output.append(f"{status_icon} Status: {status}")
        output.append(f"   Message: {message}\n")
        
        if 'database_stats' in results and results['database_stats']:
            stats = results['database_stats']
            output.append(f"{icons['chart']} Database Statistics:")
            if 'path' in stats:
                output.append(f"   Path: {stats['path']}")
            if 'size_mb' in stats:
                output.append(f"   Size: {stats['size_mb']} MB")
            if 'total_rows' in stats:
                output.append(f"   Total Rows: {stats['total_rows']}")
            if 'modified' in stats:
                output.append(f"   Modified: {stats['modified']}")
    
    if 'timestamp' in results:
        import datetime
        ts = results['timestamp']
        dt = datetime.datetime.fromtimestamp(ts)
        output.append(f"\n{icons['clock']} Checked at: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
    
    return "\n".join(output)


def format_basic_health(results: Dict[str, Any]) -> str:
    """Format basic health check results."""
    icons = _get_icons()
    output = []
    
    if 'http_status' in results:
        http_status = results['http_status']
        data = results.get('data', results)
        
        if http_status == 200:
            output.append(f"{icons['check']} HTTP Status: 200 OK\n")
        else:
            output.append(f"{icons['cross']} HTTP Status: {http_status}\n")
        
        results = data
    
    if 'error' in results:
        output.append(f"{icons['cross']} ERROR: {results['error']}")
        return "\n".join(output)
    
    output.append(f"{icons['check']} Basic Health Check\n")
    
    if 'status' in results:
        output.append(f"   Status: {results['status']}")
    if 'version' in results:
        output.append(f"   Version: {results['version']}")
    
    return "\n".join(output)


def format_status_results(results: Dict[str, Any]) -> str:
    """Format application status results."""
    icons = _get_icons()
    output = []
    
    if 'http_status' in results:
        http_status = results['http_status']
        data = results.get('data', results)
        
        if http_status == 200:
            output.append(f"{icons['check']} HTTP Status: 200 OK\n")
        else:
            output.append(f"{icons['cross']} HTTP Status: {http_status}\n")
        
        results = data
    
    if 'error' in results:
        output.append(f"{icons['cross']} ERROR: {results['error']}")
        return "\n".join(output)
    
    output.append(f"{icons['check']} Application Status\n")
    
    if 'status' in results:
        output.append(f"   Status: {results['status']}")
    if 'framework' in results:
        output.append(f"   Framework: {results['framework']}")
    if 'version' in results:
        output.append(f"   Version: {results['version']}")
    if 'uptime_seconds' in results:
        uptime = results['uptime_seconds']
        hours = int(uptime // 3600)
        minutes = int((uptime % 3600) // 60)
        output.append(f"   Uptime: {hours}h {minutes}m ({uptime:.1f}s)")
    if 'memory_percent' in results:
        output.append(f"   Memory Usage: {results['memory_percent']}%")
    if 'timestamp' in results:
        import datetime
        ts = results['timestamp']
        dt = datetime.datetime.fromtimestamp(ts)
        output.append(f"   Timestamp: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
    
    return "\n".join(output)


def format_health_results(results: Dict[str, Any]) -> str:
    """
    Format health check results for display.
    
    Args:
        results: Health check results dictionary
        
    Returns:
        Formatted string
    """
    icons = _get_icons()
    
    output = []
    
    # Check if this is a wrapped response with http_status
    if 'http_status' in results:
        http_status = results['http_status']
        data = results.get('data', results)
        
        # Display HTTP status code
        if http_status == 200:
            output.append(f"{icons['check']} HTTP Status: 200 OK (All healthy)\n")
        elif http_status == 503:
            output.append(f"{icons['warning']} HTTP Status: 503 Service Unavailable (Degraded)\n")
        elif http_status == 500:
            output.append(f"{icons['cross']} HTTP Status: 500 Internal Server Error\n")
        else:
            output.append(f"{icons['cross']} HTTP Status: {http_status} (Unexpected)\n")
        
        # Use nested data for processing
        results = data
    
    if 'error' in results:
        output.append(f"{icons['cross']} ERROR: {results['error']}")
        if 'suggestion' in results:
            output.append(f"   {icons['info']} {results['suggestion']}")
        if 'details' in results:
            output.append(f"   Details: {results['details']}")
        return "\n".join(output)
    
    # Success case
    output.append(f"{icons['check']} Health Check Results\n")
    
    # Overall status
    if 'status' in results:
        status = results['status']
        status_icon = icons['check'] if status == "success" else icons['warning']
        output.append(f"{status_icon} Overall Status: {status}\n")
        
        # Show degraded status if present
        if results.get('degraded'):
            output.append(f"{icons['warning']} Degraded: {results.get('unhealthy_count', 0)} of {results.get('total_models', 0)} models unhealthy\n")
    
    # Available models
    if 'health' in results:
        health_data = results['health']
        available_models = health_data.get('available_models', [])
        output.append(f"{icons['list']} Available Models ({len(available_models)}): {', '.join(available_models)}\n")
        
        # Model statuses
        output.append(f"\n{icons['chart']} Model Health Status:\n")
        output.append("-" * 60)
        
        for model in available_models:
            if model in health_data:
                model_info = health_data[model]
                status = model_info.get('status', 'unknown')
                
                if status == 'healthy':
                    icon = icons['check']
                    latency = model_info.get('latency', 'N/A')
                    note = model_info.get('note', '')
                    output.append(f"{icon} {model:15} | Status: {status:10} | Latency: {latency}s")
                    if note:
                        output.append(f"   L- Note: {note}")
                else:
                    icon = icons['cross']
                    error = model_info.get('error', 'Unknown error')
                    note = model_info.get('note', '')
                    output.append(f"{icon} {model:15} | Status: {status:10} | Error: {error[:50]}")
                    if note:
                        output.append(f"   L- Note: {note}")
        
        output.append("-" * 60)
        
        # Circuit breaker states
        if 'circuit_states' in health_data:
            output.append(f"\n{icons['plug']} Circuit Breaker States:\n")
            for model, state in health_data['circuit_states'].items():
                state_icon = icons['green'] if state == "closed" else icons['red'] if state == "open" else icons['yellow']
                output.append(f"   {state_icon} {model:15} | {state}")
    
    # Timestamp
    if 'timestamp' in results:
        import datetime
        ts = results['timestamp']
        dt = datetime.datetime.fromtimestamp(ts)
        output.append(f"\n{icons['clock']} Checked at: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
    
    return "\n".join(output)


async def main():
    """Main test function."""
    parser = argparse.ArgumentParser(
        description='Comprehensive health check for all MindGraph endpoints',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test all endpoints via HTTP (default: http://localhost:9527)
  python tests/test_health_check.py
  
  # Test with custom endpoint
  python tests/test_health_check.py --endpoint http://localhost:9527
  
  # Test service directly (no HTTP) - LLM only
  python tests/test_health_check.py --direct
  
  # Test both HTTP and direct service call
  python tests/test_health_check.py --both
  
  # Output as JSON
  python tests/test_health_check.py --json
        """
    )
    parser.add_argument(
        '--endpoint',
        type=str,
        default='http://localhost:9527',
        help='Base URL of the MindGraph server (default: http://localhost:9527)'
    )
    parser.add_argument(
        '--direct',
        action='store_true',
        help='Test LLM service directly instead of via HTTP endpoint'
    )
    parser.add_argument(
        '--both',
        action='store_true',
        help='Test both HTTP endpoint and direct service call'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output results as JSON'
    )
    
    args = parser.parse_args()
    
    # Test all health endpoints via HTTP
    all_results = None
    direct_results = None
    
    if not args.direct or args.both:
        all_results = await test_all_health_endpoints(args.endpoint)
        
        if args.json:
            print(json.dumps(all_results, indent=2, ensure_ascii=False))
        else:
            # Format and display each endpoint result
            for endpoint_name, result in all_results.items():
                if endpoint_name == '_total_duration':
                    continue  # Skip timing metadata
                    
                print(f"\n{'-'*60}")
                print(f"{endpoint_name}")
                print(f"{'-'*60}")
                
                # Show duration if available
                if 'duration' in result:
                    icons = _get_icons()
                    print(f"{icons['clock']} Duration: {result['duration']}s\n")
                
                if result.get('success'):
                    if endpoint_name == 'Basic Health':
                        print(format_basic_health(result))
                    elif endpoint_name == 'Application Status':
                        print(format_status_results(result))
                    elif endpoint_name == 'LLM Services Health':
                        print(format_health_results(result.get('data', result)))
                    elif endpoint_name == 'Database Health':
                        print(format_database_health(result))
                else:
                    icons = _get_icons()
                    print(f"{icons['cross']} Failed: {result.get('error', 'Unknown error')}")
            
            # Show total duration
            if '_total_duration' in all_results:
                icons = _get_icons()
                print(f"\n{icons['clock']} Total Health Check Duration: {all_results['_total_duration']}s")
    
    # Test direct service call (LLM only)
    if args.direct or args.both:
        direct_results = await test_health_direct()
        
        if args.json:
            print("\nDirect Service Call Results:")
            print(json.dumps(direct_results, indent=2, ensure_ascii=False))
        else:
            print(f"\n{'-'*60}")
            print("Direct Service Call (LLM)")
            print(f"{'-'*60}")
            print(format_health_results(direct_results))
    
    # Summary
    if not args.json:
        print(f"\n{'='*60}")
        print("Overall Summary")
        print(f"{'='*60}")
        
        icons = _get_icons()
        all_healthy = True
        issues = []
        
        # Check all endpoints
        if all_results:
            for endpoint_name, result in all_results.items():
                # Skip timing metadata
                if endpoint_name == '_total_duration':
                    continue
                if not isinstance(result, dict) or not result.get('success'):
                    print(f"{icons['cross']} {endpoint_name}: Failed - {result.get('error', 'Unknown')}")
                    all_healthy = False
                    issues.append(endpoint_name)
                else:
                    http_status = result.get('http_status', 0)
                    data = result.get('data', {})
                    
                    if endpoint_name == 'Basic Health':
                        if http_status == 200:
                            print(f"{icons['check']} {endpoint_name}: OK")
                        else:
                            print(f"{icons['cross']} {endpoint_name}: HTTP {http_status}")
                            all_healthy = False
                            issues.append(endpoint_name)
                    
                    elif endpoint_name == 'Application Status':
                        if http_status == 200:
                            print(f"{icons['check']} {endpoint_name}: OK")
                        else:
                            print(f"{icons['cross']} {endpoint_name}: HTTP {http_status}")
                            all_healthy = False
                            issues.append(endpoint_name)
                    
                    elif endpoint_name == 'LLM Services Health':
                        if http_status == 200:
                            health_data = data.get('health', {})
                            unhealthy_models = [
                                model for model in health_data.get('available_models', [])
                                if model in health_data 
                                and health_data[model].get('status') != 'healthy'
                            ]
                            if unhealthy_models:
                                print(f"{icons['warning']} {endpoint_name}: {len(unhealthy_models)} model(s) unhealthy")
                                all_healthy = False
                                issues.append(f"{endpoint_name} ({len(unhealthy_models)} models)")
                            else:
                                print(f"{icons['check']} {endpoint_name}: All models healthy")
                        elif http_status == 503:
                            unhealthy_count = data.get('unhealthy_count', 0)
                            print(f"{icons['warning']} {endpoint_name}: {unhealthy_count} model(s) unhealthy (degraded)")
                            all_healthy = False
                            issues.append(f"{endpoint_name} ({unhealthy_count} models)")
                        else:
                            print(f"{icons['cross']} {endpoint_name}: HTTP {http_status}")
                            all_healthy = False
                            issues.append(endpoint_name)
                    
                    elif endpoint_name == 'Database Health':
                        db_healthy = data.get('database_healthy', False)
                        if http_status == 200 and db_healthy:
                            print(f"{icons['check']} {endpoint_name}: Healthy")
                        elif http_status == 503 or not db_healthy:
                            print(f"{icons['cross']} {endpoint_name}: Unhealthy - {data.get('database_message', 'Unknown')}")
                            all_healthy = False
                            issues.append(endpoint_name)
                        else:
                            print(f"{icons['cross']} {endpoint_name}: HTTP {http_status}")
                            all_healthy = False
                            issues.append(endpoint_name)
        
        # Check direct service call (reuse results from above)
        if direct_results:
            if 'error' in direct_results:
                print(f"{icons['cross']} Direct Service Call: Failed")
                all_healthy = False
                issues.append("Direct Service Call")
            elif 'health' in direct_results:
                health_data = direct_results['health']
                unhealthy_models = [
                    model for model in health_data.get('available_models', [])
                    if model in health_data and health_data[model].get('status') != 'healthy'
                ]
                if unhealthy_models:
                    print(f"{icons['warning']} Direct Service Call: {len(unhealthy_models)} model(s) unhealthy")
                    all_healthy = False
                    issues.append(f"Direct Service ({len(unhealthy_models)} models)")
                else:
                    print(f"{icons['check']} Direct Service Call: All models healthy")
        
        # Final verdict
        print(f"\n{'-'*60}")
        if all_healthy:
            print(f"{icons['party']} All health checks passed! System is healthy.")
        else:
            print(f"{icons['warning']} Some health checks failed:")
            for issue in issues:
                print(f"   - {issue}")
            sys.exit(1)
    else:
        # JSON output - check for errors
        if all_results:
            for endpoint_name, result in all_results.items():
                if not result.get('success') or result.get('http_status', 0) >= 400:
                    sys.exit(1)
        if direct_results and 'error' in direct_results:
            sys.exit(1)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n[!] Test interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n[X] Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

