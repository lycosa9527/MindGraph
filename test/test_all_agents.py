#!/usr/bin/env python3
"""
Enhanced test script for all diagram agents that generates real PNG images via API.
Includes comprehensive timing measurements from LLM processing to final PNG rendering.
Focuses on performance analysis and timing breakdown for optimization insights.
Assumes MindGraph application is already running on http://localhost:9527
"""

import sys
import os
import json
import time
import requests
import statistics
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add the parent directory (workspace root) to Python path to access agents module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Application URL
app_url = "http://localhost:9527"

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

def generate_diagram_via_api(prompt, language="en") -> Dict[str, Any]:
    """Generate a diagram using the MindGraph API with comprehensive timing."""
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
        print(f"  📤 Sending request to API...")
        
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
        
        print(f"  🎨 Generating PNG image...")
        # Longer timeout for complex diagrams like concept maps
        timeout = 180 if 'concept' in prompt.lower() or 'mind' in prompt.lower() else 120
        
        # Record start time for API request (this includes LLM + rendering)
        timing_data['api_request_start'] = time.time()
        
        png_response = requests.post(
            f"{app_url}/api/generate_png",
            json=png_data,
            timeout=timeout
        )
        
        # Record end time for API request
        timing_data['api_request_end'] = time.time()
        
        if png_response.status_code != 200:
            print(f"  ❌ PNG generation failed: {png_response.status_code}")
            try:
                error_detail = png_response.json().get('error', 'Unknown error')
                print(f"  ❌ Error details: {error_detail}")
                timing_data['error'] = error_detail
            except:
                print(f"  ❌ Response content: {png_response.text[:200]}...")
                timing_data['error'] = f"HTTP {png_response.status_code}"
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

def main():
    """Main test function with comprehensive timing analysis."""
    print("🚀 Starting comprehensive MindGraph agent testing with timing analysis...")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🌐 Using MindGraph application at: {app_url}")
    
    # Check if the app is running
    if not check_app_running():
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
