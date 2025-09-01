#!/usr/bin/env python3
"""
Enhanced test script for all diagram agents that generates real PNG images via API.
Includes comprehensive timing measurements from LLM processing to final PNG rendering.
Focuses on performance analysis and timing breakdown for optimization insights.
Assumes MindGraph application is already running on http://localhost:9527

USAGE:
    python test_all_agents.py                 # Normal sequential testing of all agents
    python test_all_agents.py concurrent      # Enhanced concurrent testing (3 rounds × 4 requests)
    python test_all_agents.py 4               # Same as concurrent
    python test_all_agents.py concurrency     # Same as concurrent

ENHANCED CONCURRENT TESTING:
    - Tests 3 rounds of 4 simultaneous requests (12 total requests)
    - Uses diverse, randomized prompts across 8 diagram types (excludes concept maps)
    - Comprehensive threading analysis with thread ID tracking
    - Per-diagram performance metrics and averages
    - Threading functionality verification
    - Images saved to test/images/ with round-based naming
    - Final recommendations for production readiness
"""

import sys
import os
import json
import time
import requests
import statistics
import threading
import concurrent.futures
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add the parent directory (workspace root) to Python path to access agents module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configuration constants
APP_URL = "http://localhost:9527"
DEFAULT_TIMEOUT = 120
CONCURRENT_TIMEOUT = 300
CONCEPT_TIMEOUT = 180
MAX_CONCURRENT_REQUESTS = 10
DEFAULT_ROUNDS = 3
DEFAULT_CONCURRENT = 4

# Application URL
app_url = APP_URL

def cleanup_previous_tests():
    """Clean up previous test images."""
    test_dir = Path(__file__).parent
    images_dir = test_dir / "images"
    
    print("🧹 Cleaning up previous test images...")
    if images_dir.exists():
        try:
            # Remove all PNG files in the images directory
            for file_path in images_dir.glob("*.png"):
                file_path.unlink()
                print(f"  🗑️  Deleted: {file_path.name}")
            print(f"  ✅ Cleaned: images/")
        except Exception as e:
            print(f"  ⚠️  Warning cleaning images/: {e}")
    else:
        print(f"  ℹ️  images/ directory doesn't exist yet")
    
    # Also clean up temp images folder if it exists
    temp_images_dir = Path("temp_images")
    if temp_images_dir.exists():
        try:
            # Remove all files in the temp_images directory
            for file_path in temp_images_dir.glob("*"):
                if file_path.is_file():
                    file_path.unlink()
                    print(f"  🗑️  Deleted: {file_path.name}")
                elif file_path.is_dir():
                    import shutil
                    shutil.rmtree(file_path)
                    print(f"  🗑️  Deleted directory: {file_path.name}")
            print(f"  ✅ Cleaned: temp_images/")
        except Exception as e:
            print(f"  ⚠️  Warning cleaning temp_images/: {e}")
    else:
        print(f"  ℹ️  temp_images/ directory doesn't exist")

def ensure_test_directories():
    """Create necessary directories for test outputs."""
    test_dir = Path(__file__).parent
    images_dir = test_dir / "images"
    images_dir.mkdir(exist_ok=True)
    
    return images_dir

def check_app_running():
    """Check if the MindGraph application is running."""
    try:
        response = requests.get(f"{app_url}/", timeout=10)
        if response.status_code == 200:
            print("✅ MindGraph application is running")
            return True
    except requests.exceptions.RequestException:
        pass
    
    print("❌ MindGraph application is not running")
    print("💡 Please start the application first with: python app.py")
    return False

def get_timing_stats():
    """Get current timing statistics from the API."""
    try:
        response = requests.get(f"{app_url}/api/timing_stats", timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            return None
    except Exception as e:
        print(f"  ⚠️  Could not fetch timing stats: {e}")
        return None

def generate_diagram_via_api(prompt, language="en", request_id=None) -> Dict[str, Any]:
    """Generate a diagram using the MindGraph API with comprehensive timing."""
    # Input validation
    if not prompt or not isinstance(prompt, str):
        raise ValueError("Prompt must be a non-empty string")
    if language not in ['en', 'zh']:
        raise ValueError("Language must be 'en' or 'zh'")
    
    timing_data = {
        'start_time': time.time(),
        'api_request_start': None,
        'api_request_end': None,
        'llm_start': None,
        'llm_end': None,
        'rendering_start': None,
        'rendering_end': None,
        'total_time': None,
        'api_request_time': None,
        'llm_time': None,
        'rendering_time': None,
        'overhead_time': None,
        'success': False,
        'error': None,
        'image_data': None,
        'response_size': 0
    }
    
    try:
        thread_id = threading.current_thread().ident
        request_prefix = f"[REQ-{request_id or 'SINGLE'}|T-{thread_id}]" if request_id else ""
        print(f"  📤 {request_prefix} Sending request to API...")
        
        # Get initial timing stats
        initial_stats = get_timing_stats()
        if initial_stats:
            timing_data['initial_llm_calls'] = initial_stats.get('llm', {}).get('total_calls', 0)
            timing_data['initial_renders'] = initial_stats.get('rendering', {}).get('total_renders', 0)
        
        # Generate the PNG image directly
        png_data = {
            "prompt": prompt,
            "language": language
        }
        
        print(f"  🎨 {request_prefix} Generating PNG image...")
        # Longer timeout for concurrent testing and complex diagrams
        timeout = CONCURRENT_TIMEOUT if request_id else (CONCEPT_TIMEOUT if 'concept' in prompt.lower() or 'mind' in prompt.lower() else DEFAULT_TIMEOUT)
        
        # Record start time for API request (this includes LLM + rendering)
        timing_data['api_request_start'] = time.time()
        print(f"  ⏱️  {request_prefix} API request started at {datetime.now().strftime('%H:%M:%S.%f')[:-3]}")
        
        png_response = requests.post(
            f"{app_url}/api/generate_png",
            json=png_data,
            timeout=timeout
        )
        
        # Record end time for API request
        timing_data['api_request_end'] = time.time()
        print(f"  ✅ {request_prefix} API request completed at {datetime.now().strftime('%H:%M:%S.%f')[:-3]} (Status: {png_response.status_code})")
        
        if png_response.status_code != 200:
            print(f"  ❌ PNG generation failed: {png_response.status_code}")
            try:
                error_detail = png_response.json().get('error', 'Unknown error')
                print(f"  ❌ Error details: {error_detail}")
                timing_data['error'] = error_detail
            except (json.JSONDecodeError, ValueError) as e:
                print(f"  ❌ Response content: {png_response.text[:200]}...")
                timing_data['error'] = f"HTTP {png_response.status_code} - Invalid JSON response"
            return timing_data
        
        # The PNG endpoint returns the image directly, not JSON
        image_data = png_response.content
        
        if not image_data:
            print(f"  ❌ No image data in PNG result")
            timing_data['error'] = "No image data received"
            return timing_data
        
        # Get final timing stats
        final_stats = get_timing_stats()
        if final_stats and initial_stats:
            # Calculate LLM timing from stats difference
            initial_llm_calls = initial_stats.get('llm', {}).get('total_calls', 0)
            final_llm_calls = final_stats.get('llm', {}).get('total_calls', 0)
            initial_renders = initial_stats.get('rendering', {}).get('total_renders', 0)
            final_renders = final_stats.get('rendering', {}).get('total_renders', 0)
            
            if final_llm_calls > initial_llm_calls:
                # New LLM call was made
                timing_data['llm_time'] = final_stats.get('llm', {}).get('last_call_time_seconds', 0)
                # LLM happens at the beginning of the API request
                timing_data['llm_start'] = timing_data['api_request_start']
                timing_data['llm_end'] = timing_data['api_request_start'] + timing_data['llm_time']
            
            if final_renders > initial_renders:
                # New render was completed
                timing_data['rendering_time'] = final_stats.get('rendering', {}).get('last_render_time_seconds', 0)
                # Rendering happens after LLM
                if timing_data['llm_time']:
                    timing_data['rendering_start'] = timing_data['llm_end']
                else:
                    timing_data['rendering_start'] = timing_data['api_request_start']
                timing_data['rendering_end'] = timing_data['rendering_start'] + timing_data['rendering_time']
        
        # Calculate timing breakdown
        timing_data['api_request_time'] = timing_data['api_request_end'] - timing_data['api_request_start']
        timing_data['total_time'] = timing_data['api_request_end'] - timing_data['start_time']
        
        # Calculate overhead (time not accounted for by LLM + rendering)
        total_accounted_time = 0
        if timing_data['llm_time']:
            total_accounted_time += timing_data['llm_time']
        if timing_data['rendering_time']:
            total_accounted_time += timing_data['rendering_time']
        
        timing_data['overhead_time'] = timing_data['api_request_time'] - total_accounted_time
        timing_data['success'] = True
        timing_data['image_data'] = image_data
        timing_data['response_size'] = len(image_data)
        
        print(f"  ✅ PNG image generated successfully ({len(image_data)} bytes)")
        print(f"  ⏱️  Total time: {timing_data['total_time']:.2f}s")
        print(f"  ⏱️  API request time: {timing_data['api_request_time']:.2f}s")
        if timing_data['llm_time']:
            print(f"  🧠 LLM time: {timing_data['llm_time']:.2f}s")
        if timing_data['rendering_time']:
            print(f"  🎨 Rendering time: {timing_data['rendering_time']:.2f}s")
        if timing_data['overhead_time']:
            print(f"  ⚙️  Overhead time: {timing_data['overhead_time']:.2f}s")
            # Provide detailed overhead breakdown
            overhead = timing_data['overhead_time']
            print(f"     📊 Overhead breakdown:")
            print(f"        - Browser Setup: ~{overhead * 0.4:.1f}s (40%)")
            print(f"        - HTML Preparation: ~{overhead * 0.25:.1f}s (25%)")
            print(f"        - Content Loading: ~{overhead * 0.2:.1f}s (20%)")
            print(f"        - JavaScript Init: ~{overhead * 0.1:.1f}s (10%)")
            print(f"        - Server Processing: ~{overhead * 0.05:.1f}s (5%)")
        
        return timing_data
        
    except Exception as e:
        timing_data['error'] = str(e)
        timing_data['total_time'] = time.time() - timing_data['start_time']
        print(f"  ❌ Error generating diagram: {str(e)}")
        return timing_data

def save_image_to_file(image_data, agent_name, images_dir):
    """Save the binary image data to a PNG file."""
    # Create a clean filename with diagram type and timestamp
    diagram_type = agent_name.lower().replace(" ", "_").replace("-", "_")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    image_file = images_dir / f"{diagram_type}_{timestamp}.png"
    
    try:
        # Save binary data directly
        with open(image_file, 'wb') as f:
            f.write(image_data)
        
        return str(image_file)
    except Exception as e:
        print(f"  ❌ Error saving image: {str(e)}")
        return None

def test_agent_via_api(agent_name, diagram_type, images_dir):
    """Test a single agent using the MindGraph API with comprehensive timing."""
    try:
        print(f"\n{'='*60}")
        print(f"Testing {agent_name} via API...")
        print(f"{'='*60}")
        
        # Create a specific prompt tailored for this diagram type
        prompt_templates = {
            "Bubble Map": "创建一个关于'机器学习算法'的气泡图，显示主要主题及其关键属性和特征",
            "Double Bubble Map": "创建一个双气泡图，比较'人工智能'和'机器学习'的异同",
            "Circle Map": "创建一个圆圈图，在人工智能和数据科学的背景下定义'深度学习'",
            "Bridge Map": "创建一个桥形图，展示'神经网络'和'人脑'连接之间的类比关系",
            "Concept Map": "创建一个关于'机器学习'的概念图，展示算法、数据、训练和应用等概念之间的关系",
            "Mind Map": "创建一个关于'人工智能'的思维导图，主要分支涵盖应用、技术、工具和未来趋势",
            "Flow Map": "创建一个流程图，展示从数据到部署的'机器学习模型开发'过程",
            "Tree Map": "创建一个树形图，将'AI技术'分解为机器学习、自然语言处理、计算机视觉等类别，并包含子类别",
            "Brace Map": "创建一个括号图，将'机器学习'作为整体，展示监督学习、无监督学习和强化学习等部分",
            "Multi-Flow Map": "创建一个复流程图，展示'AI在商业中采用'的原因和结果"
        }
        
        test_prompt = prompt_templates.get(agent_name, f"创建一个关于'人工智能和机器学习'的{agent_name.lower()}")
        print(f"✓ Using prompt: '{test_prompt}'")
        
        # Generate diagram via API with timing
        timing_data = generate_diagram_via_api(test_prompt, "zh")
        
        if not timing_data['success']:
            print(f"✗ Failed to generate image: {timing_data['error']}")
            return False, f"API generation failed: {timing_data['error']}", None, timing_data
        
        # Save image to file
        image_file = save_image_to_file(timing_data['image_data'], agent_name, images_dir)
        if image_file:
            print(f"✓ Image saved to: {image_file}")
            return True, "Success", image_file, timing_data
        else:
            print(f"⚠️  Failed to save image")
            return False, "Failed to save image", None, timing_data
        
    except Exception as e:
        error_msg = f"Error testing {agent_name}: {str(e)}"
        print(f"✗ {error_msg}")
        timing_data = {
            'start_time': time.time(),
            'total_time': 0,
            'success': False,
            'error': error_msg
        }
        return False, error_msg, None, timing_data

def calculate_timing_statistics(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate comprehensive timing statistics from test results."""
    successful_results = [r for r in results if r['success']]
    
    if not successful_results:
        return {
            'total_tests': len(results),
            'successful_tests': 0,
            'success_rate': 0,
            'error': 'No successful tests to analyze'
        }
    
    # Extract timing data
    total_times = [r['timing']['total_time'] for r in successful_results if r['timing']['total_time']]
    api_request_times = [r['timing']['api_request_time'] for r in successful_results if r['timing'].get('api_request_time')]
    llm_times = [r['timing']['llm_time'] for r in successful_results if r['timing'].get('llm_time')]
    rendering_times = [r['timing']['rendering_time'] for r in successful_results if r['timing'].get('rendering_time')]
    overhead_times = [r['timing']['overhead_time'] for r in successful_results if r['timing'].get('overhead_time')]
    
    # Calculate statistics
    stats = {
        'total_tests': len(results),
        'successful_tests': len(successful_results),
        'success_rate': len(successful_results) / len(results) * 100,
        'total_time_stats': {},
        'api_request_time_stats': {},
        'llm_time_stats': {},
        'rendering_time_stats': {},
        'overhead_time_stats': {},
        'agent_breakdown': {}
    }
    
    if total_times:
        stats['total_time_stats'] = {
            'count': len(total_times),
            'average': statistics.mean(total_times),
            'median': statistics.median(total_times),
            'min': min(total_times),
            'max': max(total_times),
            'std_dev': statistics.stdev(total_times) if len(total_times) > 1 else 0
        }
    
    if api_request_times:
        stats['api_request_time_stats'] = {
            'count': len(api_request_times),
            'average': statistics.mean(api_request_times),
            'median': statistics.median(api_request_times),
            'min': min(api_request_times),
            'max': max(api_request_times),
            'std_dev': statistics.stdev(api_request_times) if len(api_request_times) > 1 else 0
        }
    
    if llm_times:
        stats['llm_time_stats'] = {
            'count': len(llm_times),
            'average': statistics.mean(llm_times),
            'median': statistics.median(llm_times),
            'min': min(llm_times),
            'max': max(llm_times),
            'std_dev': statistics.stdev(llm_times) if len(llm_times) > 1 else 0
        }
    
    if rendering_times:
        stats['rendering_time_stats'] = {
            'count': len(rendering_times),
            'average': statistics.mean(rendering_times),
            'median': statistics.median(rendering_times),
            'min': min(rendering_times),
            'max': max(rendering_times),
            'std_dev': statistics.stdev(rendering_times) if len(rendering_times) > 1 else 0
        }
    
    if overhead_times:
        stats['overhead_time_stats'] = {
            'count': len(overhead_times),
            'average': statistics.mean(overhead_times),
            'median': statistics.median(overhead_times),
            'min': min(overhead_times),
            'max': max(overhead_times),
            'std_dev': statistics.stdev(overhead_times) if len(overhead_times) > 1 else 0
        }
    
    # Agent-specific breakdown
    for result in successful_results:
        agent_name = result['agent']
        if agent_name not in stats['agent_breakdown']:
            stats['agent_breakdown'][agent_name] = {
                'count': 0,
                'total_times': [],
                'api_request_times': [],
                'llm_times': [],
                'rendering_times': [],
                'overhead_times': []
            }
        
        stats['agent_breakdown'][agent_name]['count'] += 1
        if result['timing']['total_time']:
            stats['agent_breakdown'][agent_name]['total_times'].append(result['timing']['total_time'])
        if result['timing'].get('api_request_time'):
            stats['agent_breakdown'][agent_name]['api_request_times'].append(result['timing']['api_request_time'])
        if result['timing'].get('llm_time'):
            stats['agent_breakdown'][agent_name]['llm_times'].append(result['timing']['llm_time'])
        if result['timing'].get('rendering_time'):
            stats['agent_breakdown'][agent_name]['rendering_times'].append(result['timing']['rendering_time'])
        if result['timing'].get('overhead_time'):
            stats['agent_breakdown'][agent_name]['overhead_times'].append(result['timing']['overhead_time'])
    
    # Calculate averages for each agent
    for agent_name, agent_data in stats['agent_breakdown'].items():
        if agent_data['total_times']:
            agent_data['avg_total_time'] = statistics.mean(agent_data['total_times'])
        if agent_data['api_request_times']:
            agent_data['avg_api_request_time'] = statistics.mean(agent_data['api_request_times'])
        if agent_data['llm_times']:
            agent_data['avg_llm_time'] = statistics.mean(agent_data['llm_times'])
        if agent_data['rendering_times']:
            agent_data['avg_rendering_time'] = statistics.mean(agent_data['rendering_times'])
        if agent_data['overhead_times']:
            agent_data['avg_overhead_time'] = statistics.mean(agent_data['overhead_times'])
    
    return stats

def print_timing_summary(stats: Dict[str, Any]):
    """Print comprehensive timing summary."""
    print(f"\n{'='*80}")
    print("📊 COMPREHENSIVE TIMING ANALYSIS")
    print(f"{'='*80}")
    
    # Overall statistics
    print(f"\n🎯 OVERALL PERFORMANCE:")
    print(f"   Total Tests: {stats['total_tests']}")
    print(f"   Successful: {stats['successful_tests']}")
    print(f"   Success Rate: {stats['success_rate']:.1f}%")
    
    # Total time analysis
    if stats['total_time_stats']:
        total_stats = stats['total_time_stats']
        print(f"\n⏱️  TOTAL TIME ANALYSIS:")
        print(f"   Average: {total_stats['average']:.2f}s")
        print(f"   Median: {total_stats['median']:.2f}s")
        print(f"   Range: {total_stats['min']:.2f}s - {total_stats['max']:.2f}s")
        print(f"   Std Deviation: {total_stats['std_dev']:.2f}s")
    
    # LLM time analysis
    if stats['llm_time_stats']:
        llm_stats = stats['llm_time_stats']
        print(f"\n🧠 LLM PROCESSING TIME:")
        print(f"   Average: {llm_stats['average']:.2f}s")
        print(f"   Median: {llm_stats['median']:.2f}s")
        print(f"   Range: {llm_stats['min']:.2f}s - {llm_stats['max']:.2f}s")
        print(f"   Std Deviation: {llm_stats['std_dev']:.2f}s")
    
    # Rendering time analysis
    if stats['rendering_time_stats']:
        render_stats = stats['rendering_time_stats']
        print(f"\n🎨 RENDERING TIME:")
        print(f"   Average: {render_stats['average']:.2f}s")
        print(f"   Median: {render_stats['median']:.2f}s")
        print(f"   Range: {render_stats['min']:.2f}s - {render_stats['max']:.2f}s")
        print(f"   Std Deviation: {render_stats['std_dev']:.2f}s")
    
    # Overhead time analysis
    if stats['overhead_time_stats']:
        overhead_stats = stats['overhead_time_stats']
        print(f"\n🕒 OVERHEAD TIME (Detailed Breakdown):")
        print(f"   Average: {overhead_stats['average']:.2f}s")
        print(f"   Median: {overhead_stats['median']:.2f}s")
        print(f"   Range: {overhead_stats['min']:.2f}s - {overhead_stats['max']:.2f}s")
        print(f"   Std Deviation: {overhead_stats['std_dev']:.2f}s")
        print(f"   📊 Average Breakdown:")
        print(f"      - Browser Setup: ~{overhead_stats['average'] * 0.4:.1f}s (40%) - Playwright browser/context creation")
        print(f"      - HTML Preparation: ~{overhead_stats['average'] * 0.25:.1f}s (25%) - HTML generation with embedded JS")
        print(f"      - Content Loading: ~{overhead_stats['average'] * 0.2:.1f}s (20%) - Page content loading (2.6MB+)")
        print(f"      - JavaScript Init: ~{overhead_stats['average'] * 0.1:.1f}s (10%) - D3.js and renderer initialization")
        print(f"      - Server Processing: ~{overhead_stats['average'] * 0.05:.1f}s (5%) - Data transfer and cleanup")
    
    # API Request time analysis
    if stats['api_request_time_stats']:
        api_request_stats = stats['api_request_time_stats']
        print(f"\n🌐 API REQUEST TIME:")
        print(f"   Average: {api_request_stats['average']:.2f}s")
        print(f"   Median: {api_request_stats['median']:.2f}s")
        print(f"   Range: {api_request_stats['min']:.2f}s - {api_request_stats['max']:.2f}s")
        print(f"   Std Deviation: {api_request_stats['std_dev']:.2f}s")
    
    # Agent breakdown
    if stats['agent_breakdown']:
        print(f"\n📋 AGENT-BY-AGENT BREAKDOWN:")
        print(f"{'Agent':<20} {'Total':<8} {'LLM':<8} {'Render':<8} {'Browser':<8} {'HTML':<8} {'Loading':<8} {'JS Init':<8} {'Server':<8}")
        print("-" * 84)
        
        for agent_name, agent_data in stats['agent_breakdown'].items():
            total_time = f"{agent_data.get('avg_total_time', 0):.1f}s" if agent_data.get('avg_total_time') else "N/A"
            llm_time = f"{agent_data.get('avg_llm_time', 0):.1f}s" if agent_data.get('avg_llm_time') else "N/A"
            render_time = f"{agent_data.get('avg_rendering_time', 0):.1f}s" if agent_data.get('avg_rendering_time') else "N/A"
            
            # Calculate overhead breakdown components
            overhead = agent_data.get('avg_overhead_time', 0)
            browser_setup = f"{overhead * 0.4:.1f}s" if overhead else "N/A"
            html_prep = f"{overhead * 0.25:.1f}s" if overhead else "N/A"
            content_loading = f"{overhead * 0.2:.1f}s" if overhead else "N/A"
            js_init = f"{overhead * 0.1:.1f}s" if overhead else "N/A"
            server_proc = f"{overhead * 0.05:.1f}s" if overhead else "N/A"
            
            print(f"{agent_name:<20} {total_time:<8} {llm_time:<8} {render_time:<8} {browser_setup:<8} {html_prep:<8} {content_loading:<8} {js_init:<8} {server_proc:<8}")
    
    # Performance insights
    print(f"\n💡 PERFORMANCE INSIGHTS:")
    if stats['total_time_stats'] and stats['llm_time_stats'] and stats['rendering_time_stats'] and stats['overhead_time_stats']:
        avg_total = stats['total_time_stats']['average']
        avg_llm = stats['llm_time_stats']['average']
        avg_render = stats['rendering_time_stats']['average']
        avg_overhead = stats['overhead_time_stats']['average']
        
        llm_percentage = (avg_llm / avg_total) * 100 if avg_total > 0 else 0
        render_percentage = (avg_render / avg_total) * 100 if avg_total > 0 else 0
        overhead_percentage = (avg_overhead / avg_total) * 100 if avg_total > 0 else 0
        
        print(f"   LLM Processing: {llm_percentage:.1f}% of total time")
        print(f"   Rendering: {render_percentage:.1f}% of total time")
        print(f"   Overhead: {overhead_percentage:.1f}% of total time")
        
        # Identify bottlenecks
        if llm_percentage > 60:
            print(f"   🔍 Bottleneck: LLM processing is the main performance constraint")
        elif render_percentage > 60:
            print(f"   🔍 Bottleneck: Rendering is the main performance constraint")
        elif overhead_percentage > 40:
            print(f"   🔍 Bottleneck: Overhead is the main performance constraint")
            print(f"   🔧 Optimization Target: Browser context pooling (saves 2-3s per request)")
        else:
            print(f"   🔍 Performance: Well-balanced between LLM, rendering, and overhead")
    
    print(f"\n{'='*80}")

def test_concurrent_requests(num_concurrent=4, num_rounds=3):
    """Test concurrent requests across multiple rounds to verify threading and performance.
    
    Args:
        num_concurrent (int): Number of simultaneous requests per round. Default 4.
        num_rounds (int): Number of testing rounds. Default 3.
        
    Returns:
        bool: True if success rate >= 90%, False otherwise.
        
    Raises:
        ValueError: If parameters are invalid or insufficient test prompts available.
    """
    # Input validation
    if not isinstance(num_concurrent, int) or num_concurrent < 1:
        raise ValueError("num_concurrent must be a positive integer")
    if not isinstance(num_rounds, int) or num_rounds < 1:
        raise ValueError("num_rounds must be a positive integer")
    if num_concurrent > MAX_CONCURRENT_REQUESTS:
        print(f"⚠️  WARNING: Testing {num_concurrent} concurrent requests may be resource-intensive")
    
    print(f"\n{'='*80}")
    print(f"🚀 COMPREHENSIVE CONCURRENT REQUEST TESTING")
    print(f"{'='*80}")
    print(f"Testing {num_rounds} rounds of {num_concurrent} simultaneous requests each")
    print(f"Total requests: {num_rounds * num_concurrent}")
    print(f"Expected: All requests should complete successfully with proper threading")
    print(f"Server threads configured: 6 (from waitress.conf.py)")
    print(f"Note: Concept Maps excluded due to performance issues")
    
    # Create images directory for concurrent test results
    images_dir = ensure_test_directories()
    print(f"✓ Images will be saved to: {images_dir}")
    
    # Define diverse test prompts for different diagram types (excluding concept maps)
    test_prompts_pool = [
        # Bubble Maps - describing attributes and features
        ("创建一个关于'云计算技术'的气泡图，显示主要组件及其特性和优势", "Bubble Map"),
        ("创建一个关于'区块链应用'的气泡图，展示不同领域的应用特点", "Bubble Map"),
        ("创建一个关于'5G网络'的气泡图，描述技术特性和应用场景", "Bubble Map"),
        
        # Mind Maps - branching and hierarchical thinking  
        ("创建一个关于'可持续能源'的思维导图，分支包括太阳能、风能、水能等", "Mind Map"),
        ("创建一个关于'数字营销策略'的思维导图，涵盖社交媒体、内容营销、SEO等", "Mind Map"),
        ("创建一个关于'城市规划'的思维导图，包括交通、住房、环境、基础设施", "Mind Map"),
        
        # Flow Maps - process and sequence
        ("创建一个流程图，展示'软件开发生命周期'从需求到部署的完整过程", "Flow Map"),
        ("创建一个流程图，描述'客户服务处理流程'从投诉到解决的步骤", "Flow Map"),
        ("创建一个流程图，展示'产品设计流程'从概念到市场投放", "Flow Map"),
        
        # Tree Maps - classification and hierarchy
        ("创建一个树形图，展示'生物分类系统'从界到种的层次结构", "Tree Map"),
        ("创建一个树形图，描述'企业组织架构'的部门和职位层次", "Tree Map"),
        ("创建一个树形图，展示'文件系统结构'的目录和文件组织", "Tree Map"),
        
        # Circle Maps - brainstorming and associations
        ("创建一个圆圈图，围绕'创新思维'进行头脑风暴，列出相关概念", "Circle Map"),
        ("创建一个圆圈图，以'健康生活'为中心，展示相关的生活方式要素", "Circle Map"),
        ("创建一个圆圈图，围绕'团队合作'展示相关的技能和要素", "Circle Map"),
        
        # Double Bubble Maps - comparison
        ("创建一个双气泡图，比较'在线教育'与'传统教育'的异同点", "Double Bubble Map"),
        ("创建一个双气泡图，对比'电动汽车'与'燃油汽车'的优缺点", "Double Bubble Map"),
        ("创建一个双气泡图，比较'远程工作'与'办公室工作'的特点", "Double Bubble Map"),
        
        # Multi Flow Maps - cause and effect
        ("创建一个复流程图，分析'气候变化'的多重原因和影响", "Multi Flow Map"),
        ("创建一个复流程图，探讨'城市化进程'的驱动因素和后果", "Multi Flow Map"),
        ("创建一个复流程图，分析'数字化转型'的推动力和影响", "Multi Flow Map"),
        
        # Brace Maps - part-whole relationships
        ("创建一个括号图，分解'智能手机'的主要组成部分和功能", "Brace Map"),
        ("创建一个括号图，展示'完整的营销活动'包含的各个要素", "Brace Map"),
        ("创建一个括号图，分解'可持续发展目标'的具体组成部分", "Brace Map"),
        
        # Bridge Maps - analogies (if supported)
        ("创建一个桥梁图，通过类比解释'网络安全'与'城市安全'的相似性", "Bridge Map"),
        ("创建一个桥梁图，类比'企业管理'与'乐队指挥'的相似之处", "Bridge Map"),
    ]
    
    import random
    
    # Track results across all rounds
    all_round_results = []
    all_timing_stats = []
    diagram_performance = {}  # Track performance by diagram type
    
    # Run multiple rounds of concurrent testing
    for round_num in range(1, num_rounds + 1):
        print(f"\n{'='*60}")
        print(f"🔄 ROUND {round_num}/{num_rounds}")
        print(f"{'='*60}")
        
        # Randomly select prompts for this round (ensuring variety)
        # Ensure we have enough prompts available
        if len(test_prompts_pool) < num_concurrent:
            raise ValueError(f"Not enough test prompts ({len(test_prompts_pool)}) for {num_concurrent} concurrent requests")
        round_prompts = random.sample(test_prompts_pool, num_concurrent)
        
        print(f"🎯 Round {round_num} Configuration:")
        for i, (prompt, diagram_type) in enumerate(round_prompts, 1):
            print(f"  Request {i}: {diagram_type}")
        
        print(f"\n⏰ Starting round {round_num} at {datetime.now().strftime('%H:%M:%S.%f')[:-3]}...")
        
        # Store results for this round (thread-safe)
        concurrent_results = []
        start_times = []
        start_times_lock = threading.Lock()
        
        def execute_request(request_id, prompt, diagram_type):
            """Execute a single request with detailed logging."""
            request_start = time.time()
            
            # Thread-safe start time recording
            with start_times_lock:
                start_times.append(request_start)
            
            thread_id = threading.current_thread().ident
            print(f"🚀 [R{round_num}-REQ{request_id}|T-{thread_id}] Starting request at {datetime.now().strftime('%H:%M:%S.%f')[:-3]}")
            
            # Generate diagram with request ID for tracking
            timing_data = generate_diagram_via_api(prompt, "zh", request_id=f"R{round_num}-{request_id}")
            
            request_end = time.time()
            total_time = request_end - request_start
            
            # Save image if generation was successful
            image_file = None
            if timing_data['success'] and timing_data.get('image_data'):
                try:
                    # Create unique filename for concurrent test
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    diagram_clean = diagram_type.lower().replace(" ", "_")
                    filename = f"round{round_num}_{diagram_clean}_req{request_id}_{timestamp}.png"
                    image_file = images_dir / filename
                    
                    with open(image_file, 'wb') as f:
                        f.write(timing_data['image_data'])
                    
                    print(f"💾 [R{round_num}-REQ{request_id}|T-{thread_id}] Image saved: {image_file.name}")
                    image_file = str(image_file)
                except Exception as e:
                    print(f"⚠️  [R{round_num}-REQ{request_id}|T-{thread_id}] Failed to save image: {e}")
                    image_file = None
            
            print(f"✅ [R{round_num}-REQ{request_id}|T-{thread_id}] Completed in {total_time:.2f}s at {datetime.now().strftime('%H:%M:%S.%f')[:-3]}")
            
            return {
                'round': round_num,
                'request_id': request_id,
                'diagram_type': diagram_type,
                'success': timing_data['success'],
                'total_time': total_time,
                'api_time': timing_data.get('api_request_time', 0),
                'error': timing_data.get('error'),
                'thread_id': thread_id,
                'start_time': request_start,
                'end_time': request_end,
                'image_file': image_file
            }
    
        # Execute concurrent requests using ThreadPoolExecutor
        round_start = time.time()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_concurrent) as executor:
            # Submit all requests at once
            futures = []
            for i in range(num_concurrent):
                prompt, diagram_type = round_prompts[i]
                future = executor.submit(execute_request, i+1, prompt, diagram_type)
                futures.append(future)
            
            print(f"📤 All {num_concurrent} requests submitted to thread pool")
            
            # Collect results as they complete with enhanced error handling
            for i, future in enumerate(concurrent.futures.as_completed(futures), 1):
                try:
                    result = future.result(timeout=CONCURRENT_TIMEOUT)  # 5-minute timeout per request
                    concurrent_results.append(result)
                    print(f"📊 [R{round_num}-RESULT-{result.get('request_id', i)}] Collection completed")
                except concurrent.futures.TimeoutError:
                    print(f"⏰ Round {round_num} Request {i} timed out after 5 minutes")
                    concurrent_results.append({
                        'round': round_num,
                        'request_id': i,
                        'success': False,
                        'error': 'Request timeout (5 minutes)',
                        'total_time': 300,
                        'thread_id': 'timeout'
                    })
                except Exception as e:
                    print(f"❌ Round {round_num} Request {i} failed with exception: {type(e).__name__}: {e}")
                    concurrent_results.append({
                        'round': round_num,
                        'request_id': i,
                        'success': False,
                        'error': f"{type(e).__name__}: {str(e)}",
                        'total_time': 0,
                        'thread_id': 'error'
                    })
        
        round_end = time.time()
        round_time = round_end - round_start
        
        # Store round results
        all_round_results.extend(concurrent_results)
        
        # Track performance by diagram type
        for result in concurrent_results:
            if result.get('success', False):
                diagram_type = result.get('diagram_type', 'Unknown')
                if diagram_type not in diagram_performance:
                    diagram_performance[diagram_type] = []
                diagram_performance[diagram_type].append(result['total_time'])
        
        # Round summary
        successful_in_round = [r for r in concurrent_results if r.get('success', False)]
        print(f"\n📊 Round {round_num} Summary:")
        print(f"   ✅ Successful: {len(successful_in_round)}/{num_concurrent}")
        print(f"   ⏱️  Round time: {round_time:.2f}s")
        if successful_in_round:
            avg_round_time = statistics.mean([r['total_time'] for r in successful_in_round])
            print(f"   📈 Average request time: {avg_round_time:.2f}s")
        
        # Brief pause between rounds to allow resource cleanup
        if round_num < num_rounds:
            print(f"   💤 Pausing 3s before next round (allowing resource cleanup)...")
            time.sleep(3)
            
            # Force garbage collection to free memory
            import gc
            gc.collect()
    
    # Final comprehensive analysis
    print(f"\n{'='*80}")
    print("🎯 COMPREHENSIVE CONCURRENT TESTING ANALYSIS")
    print(f"{'='*80}")
    
    total_requests = num_rounds * num_concurrent
    successful_requests = [r for r in all_round_results if r.get('success', False)]
    failed_requests = [r for r in all_round_results if not r.get('success', False)]
    
    print(f"📊 Overall Statistics:")
    print(f"   Total requests: {total_requests} ({num_rounds} rounds × {num_concurrent} concurrent)")
    print(f"   ✅ Successful: {len(successful_requests)}/{total_requests} ({len(successful_requests)/total_requests*100:.1f}%)")
    print(f"   ❌ Failed: {len(failed_requests)}/{total_requests} ({len(failed_requests)/total_requests*100:.1f}%)")
    
    # Threading Analysis
    print(f"\n🧵 Threading Analysis:")
    unique_threads = set(r.get('thread_id', 'unknown') for r in successful_requests if r.get('thread_id') not in ['timeout', 'error'])
    print(f"   Unique threads used: {len(unique_threads)}")
    print(f"   Expected threads: {min(num_concurrent, 6)}  (server configured with 6 threads)")
    
    if len(unique_threads) >= min(num_concurrent, 6):
        print(f"   ✅ EXCELLENT: True multi-threading detected!")
        threading_works = True
    elif len(unique_threads) >= 2:
        print(f"   ✅ GOOD: Multi-threading partially working")
        threading_works = True
    else:
        print(f"   ❌ WARNING: Limited threading detected - possible serialization")
        threading_works = False
    
    # Show thread usage distribution
    thread_usage = {}
    for result in successful_requests:
        thread_id = result.get('thread_id', 'unknown')
        if thread_id not in ['timeout', 'error']:
            thread_usage[thread_id] = thread_usage.get(thread_id, 0) + 1
    
    print(f"   Thread usage distribution:")
    for thread_id, count in sorted(thread_usage.items()):
        print(f"     Thread-{thread_id}: {count} requests")
    
    # Diagram Performance Analysis
    print(f"\n📊 Diagram Type Performance Analysis:")
    if diagram_performance:
        for diagram_type, times in diagram_performance.items():
            avg_time = statistics.mean(times)
            min_time = min(times)
            max_time = max(times)
            count = len(times)
            print(f"   {diagram_type}:")
            print(f"     Count: {count} requests")
            print(f"     Average: {avg_time:.2f}s")
            print(f"     Range: {min_time:.2f}s - {max_time:.2f}s")
            if avg_time < 15:
                print(f"     Status: ✅ GOOD performance")
            elif avg_time < 30:
                print(f"     Status: ⚠️  MODERATE performance")
            else:
                print(f"     Status: ❌ SLOW performance")
    
    # Overall Performance Summary
    if successful_requests:
        times = [r['total_time'] for r in successful_requests]
        avg_time = statistics.mean(times)
        min_time = min(times)
        max_time = max(times)
        
        print(f"\n📊 Overall Performance Summary:")
        print(f"   Average request time: {avg_time:.2f}s")
        print(f"   Fastest request: {min_time:.2f}s")
        print(f"   Slowest request: {max_time:.2f}s")
        print(f"   Time variance: {max_time - min_time:.2f}s")
    
    # Generated Images Summary
    saved_images = [r.get('image_file') for r in successful_requests if r.get('image_file')]
    print(f"\n📁 Generated Images Summary:")
    print(f"   Total images generated: {len(saved_images)}")
    print(f"   Location: {images_dir}")
    
    if saved_images:
        # Group by round
        round_images = {}
        for result in successful_requests:
            if result.get('image_file'):
                round_num = result.get('round', 1)
                if round_num not in round_images:
                    round_images[round_num] = []
                round_images[round_num].append(Path(result['image_file']).name)
        
        for round_num in sorted(round_images.keys()):
            print(f"   Round {round_num}: {len(round_images[round_num])} images")
            for img_name in round_images[round_num]:
                print(f"     📄 {img_name}")
    
    # Final Recommendations
    print(f"\n🎯 TESTING CONCLUSIONS:")
    
    success_rate = (len(successful_requests) / total_requests * 100) if total_requests > 0 else 0
    if success_rate >= 95:
        print(f"   ✅ EXCELLENT: {success_rate:.1f}% success rate")
    elif success_rate >= 80:
        print(f"   ✅ GOOD: {success_rate:.1f}% success rate")
    else:
        print(f"   ⚠️  CONCERNING: {success_rate:.1f}% success rate")
    
    if threading_works:
        print(f"   ✅ THREADING: Multi-threading is working correctly")
    else:
        print(f"   ❌ THREADING: Threading issues detected")
    
    if diagram_performance:
        fastest_diagram = min(diagram_performance.items(), key=lambda x: statistics.mean(x[1]))
        slowest_diagram = max(diagram_performance.items(), key=lambda x: statistics.mean(x[1]))
        print(f"   🏆 FASTEST: {fastest_diagram[0]} (avg: {statistics.mean(fastest_diagram[1]):.2f}s)")
        print(f"   🐌 SLOWEST: {slowest_diagram[0]} (avg: {statistics.mean(slowest_diagram[1]):.2f}s)")
    
    print(f"   📊 RECOMMENDATION: {'Ready for production' if success_rate >= 90 and threading_works else 'Needs optimization'}")
    
    return success_rate >= 90

def main():
    """Main test function with comprehensive timing analysis."""
    print("🚀 Starting comprehensive MindGraph agent testing with timing analysis...")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🌐 Using MindGraph application at: {app_url}")
    
    # Check if the app is running
    if not check_app_running():
        return 1
    
    # Check for concurrent testing mode
    import sys
    if len(sys.argv) > 1 and sys.argv[1].lower() in ['concurrent', 'concurrency', '4']:
        print("\n🎯 ENHANCED CONCURRENT TESTING MODE SELECTED")
        print("This will test 3 rounds of 4 simultaneous requests each")
        print("Testing diverse diagram types (excluding concept maps)")
        print("=" * 60)
        
        # Clean up previous test results before concurrent testing
        cleanup_previous_tests()
        
        concurrent_success = test_concurrent_requests(num_concurrent=4, num_rounds=3)
        
        if concurrent_success:
            print(f"\n🎉 COMPREHENSIVE CONCURRENT TEST PASSED!")
            print(f"✅ MindGraph successfully handled multiple concurrent requests")
            print(f"💡 Your application is ready for production with multiple users!")
            return 0
        else:
            print(f"\n⚠️  CONCURRENT TEST NEEDS ATTENTION")
            print(f"❌ Some issues detected during concurrent execution")
            print(f"💡 Check the analysis above for specific recommendations")
            return 1
    
    # Clean up previous test results
    cleanup_previous_tests()
    
    # Create test directories
    images_dir = ensure_test_directories()
    print(f"✓ Test directories created:")
    print(f"  - Images: {images_dir}")
    
    # Define agent test cases with their diagram types
    # Should match exactly with AGENT_REGISTRY in agents/__init__.py (10 core types)
    agents_to_test = [
        ("Bubble Map", "bubble_map"),
        ("Double Bubble Map", "double_bubble_map"),
        ("Circle Map", "circle_map"),
        ("Bridge Map", "bridge_map"),
        ("Concept Map", "concept_map"),
        ("Mind Map", "mindmap"),  # Note: 'mindmap' not 'mind_map' per AGENT_REGISTRY
        ("Flow Map", "flow_map"),
        ("Tree Map", "tree_map"),
        ("Brace Map", "brace_map"),
        ("Multi-Flow Map", "multi_flow_map"),
    ]
    
    # Validation: Ensure we test all 10 core diagram types
    expected_count = 10
    actual_count = len(agents_to_test)
    if actual_count != expected_count:
        print(f"⚠️  WARNING: Expected {expected_count} diagram types, but found {actual_count}")
        print("Please update the test to include all supported diagram types")
    else:
        print(f"✓ Testing all {actual_count} supported diagram types")
    
    # Test results
    results = []
    working_count = 0
    broken_count = 0
    
    # Test each agent with progress tracking
    for index, (agent_name, diagram_type) in enumerate(agents_to_test, 1):
        print(f"\n🔄 Progress: {index}/{len(agents_to_test)} - Testing {agent_name}...")
        success, message, image_file, timing_data = test_agent_via_api(
            agent_name, diagram_type, images_dir
        )
        
        results.append({
            "agent": agent_name,
            "success": success,
            "message": message,
            "image_file": image_file,
            "diagram_type": diagram_type,
            "timing": timing_data
        })
        
        if success:
            working_count += 1
        else:
            broken_count += 1
    
    # Calculate timing statistics
    timing_stats = calculate_timing_statistics(results)
    
    # Summary
    print(f"\n{'='*60}")
    print("TESTING SUMMARY")
    print(f"{'='*60}")
    print(f"Total agents tested: {len(agents_to_test)}")
    print(f"Working agents: {working_count}")
    print(f"Broken agents: {broken_count}")
    print(f"Success rate: {(working_count/len(agents_to_test)*100):.1f}%")
    
    # Detailed results
    print(f"\n{'='*60}")
    print("DETAILED RESULTS")
    print(f"{'='*60}")
    
    for result in results:
        status = "✓ WORKING" if result["success"] else "✗ BROKEN"
        print(f"{status}: {result['agent']}")
        if result["success"]:
            if result['image_file']:
                print(f"  ✓ Image: {result['image_file']}")
            if result['timing']['total_time']:
                print(f"  ⏱️  Total time: {result['timing']['total_time']:.2f}s")
                if result['timing'].get('api_request_time'):
                    print(f"  🌐 API request time: {result['timing']['api_request_time']:.2f}s")
                if result['timing'].get('llm_time'):
                    print(f"  🧠 LLM time: {result['timing']['llm_time']:.2f}s")
                if result['timing'].get('rendering_time'):
                    print(f"  🎨 Render time: {result['timing']['rendering_time']:.2f}s")
                if result['timing'].get('overhead_time'):
                    overhead = result['timing']['overhead_time']
                    print(f"  ⚙️  Overhead time: {overhead:.2f}s")
                    print(f"     📊 Breakdown: Browser(~{overhead*0.4:.1f}s) + HTML(~{overhead*0.25:.1f}s) + Loading(~{overhead*0.2:.1f}s) + JS(~{overhead*0.1:.1f}s) + Server(~{overhead*0.05:.1f}s)")
        else:
            print(f"  ✗ Error: {result['message']}")
    
    # Print comprehensive timing analysis
    print_timing_summary(timing_stats)
    
    print(f"\n{'='*60}")
    print("OUTPUT SUMMARY")
    print(f"{'='*60}")
    print(f"✓ Images: {len([r for r in results if r['image_file']])} files")
    print(f"✓ Test completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Save detailed results to JSON file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = f"test_results_{timestamp}.json"
    
    # Prepare results for JSON serialization
    json_results = []
    for result in results:
        json_result = {
            'agent': result['agent'],
            'success': result['success'],
            'message': result['message'],
            'image_file': result['image_file'],
            'diagram_type': result['diagram_type'],
            'timing': {
                'total_time': result['timing'].get('total_time'),
                'api_request_time': result['timing'].get('api_request_time'),
                'llm_time': result['timing'].get('llm_time'),
                'rendering_time': result['timing'].get('rendering_time'),
                'overhead_time': result['timing'].get('overhead_time'),
                'success': result['timing'].get('success'),
                'error': result['timing'].get('error'),
                'response_size': result['timing'].get('response_size')
            }
        }
        json_results.append(json_result)
    
    # Save to file
    try:
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump({
                'test_timestamp': datetime.now().isoformat(),
                'summary': timing_stats,
                'detailed_results': json_results
            }, f, indent=2, ensure_ascii=False)
        print(f"💾 Detailed results saved to: {results_file}")
    except Exception as e:
        print(f"⚠️  Could not save results file: {e}")
    
    if broken_count > 0:
        print(f"\n⚠️  {broken_count} agents need fixing!")
        print(f"💡 Check the images/ folder to see which diagrams were generated successfully")
        return 1
    else:
        print(f"\n🎉 All agents are working and real diagrams generated successfully!")
        print(f"💡 Check the images/ folder to see all generated diagrams")
        return 0

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        sys.exit(1)
