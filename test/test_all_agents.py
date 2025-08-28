#!/usr/bin/env python3
"""
Simplified test script for all diagram agents that generates real PNG images via API.
Focuses only on image generation - no specs, results, or HTML viewer.
Assumes MindGraph application is already running on http://localhost:9527
"""

import sys
import os
import json
import time
import requests
from datetime import datetime
from pathlib import Path

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

def generate_diagram_via_api(prompt, diagram_type, language="en"):
    """Generate a diagram using the MindGraph API."""
    try:
        print(f"  📤 Sending request to API...")
        
        # Generate the PNG image directly
        png_data = {
            "prompt": prompt,
            "language": language
        }
        
        print(f"  🎨 Generating PNG image...")
        png_response = requests.post(
            f"{app_url}/api/generate_png",
            json=png_data,
            timeout=120  # PNG generation takes longer
        )
        
        if png_response.status_code != 200:
            print(f"  ❌ PNG generation failed: {png_response.status_code}")
            return None
        
        # The PNG endpoint returns the image directly, not JSON
        image_data = png_response.content
        
        if not image_data:
            print(f"  ❌ No image data in PNG result")
            return None
        
        print(f"  ✅ PNG image generated successfully ({len(image_data)} bytes)")
        return image_data
        
    except Exception as e:
        print(f"  ❌ Error generating diagram: {str(e)}")
        return None



def save_image_to_file(image_data, agent_name, images_dir):
    """Save the binary image data to a PNG file."""
    safe_name = agent_name.lower().replace(" ", "_").replace("-", "_")
    image_file = images_dir / f"{safe_name}_diagram.png"
    
    try:
        # Save binary data directly
        with open(image_file, 'wb') as f:
            f.write(image_data)
        
        return str(image_file)
    except Exception as e:
        print(f"  ❌ Error saving image: {str(e)}")
        return None



def test_agent_via_api(agent_name, diagram_type, images_dir):
    """Test a single agent using the MindGraph API."""
    try:
        print(f"\n{'='*60}")
        print(f"Testing {agent_name} via API...")
        print(f"{'='*60}")
        
        # Create a specific prompt for this diagram type
        test_prompt = f"Create a {agent_name.lower()} about 'Artificial Intelligence and Machine Learning' with detailed content and clear structure"
        print(f"✓ Using prompt: '{test_prompt}'")
        
        # Generate diagram via API
        image_data = generate_diagram_via_api(test_prompt, diagram_type, "en")
        
        if not image_data:
            print(f"✗ Failed to generate image")
            return False, f"API generation failed", None
        
        # Save image to file
        image_file = save_image_to_file(image_data, agent_name, images_dir)
        if image_file:
            print(f"✓ Image saved to: {image_file}")
            return True, "Success", image_file
        else:
            print(f"⚠️  Failed to save image")
            return False, "Failed to save image", None
        
    except Exception as e:
        error_msg = f"Error testing {agent_name}: {str(e)}"
        print(f"✗ {error_msg}")
        return False, error_msg, None

def main():
    """Main test function."""
    print("🚀 Starting comprehensive MindGraph agent testing with real API calls...")
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
    agents_to_test = [
        ("Bubble Map", "bubble_map"),
        ("Double Bubble Map", "double_bubble_map"),
        ("Circle Map", "circle_map"),
        ("Bridge Map", "bridge_map"),
        ("Concept Map", "concept_map"),
        ("Mind Map", "mindmap"),
        ("Flow Map", "flow_map"),
        ("Tree Map", "tree_map"),
        ("Brace Map", "brace_map"),
        ("Multi-Flow Map", "multi_flow_map"),
    ]
    
    # Test results
    results = []
    working_count = 0
    broken_count = 0
    
    # Test each agent
    for agent_name, diagram_type in agents_to_test:
        success, message, image_file = test_agent_via_api(
            agent_name, diagram_type, images_dir
        )
        
        results.append({
            "agent": agent_name,
            "success": success,
            "message": message,
            "image_file": image_file,
            "diagram_type": diagram_type
        })
        
        if success:
            working_count += 1
        else:
            broken_count += 1
    

    
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
        else:
            print(f"  ✗ Error: {result['message']}")
    
    print(f"\n{'='*60}")
    print("OUTPUT SUMMARY")
    print(f"{'='*60}")
    print(f"✓ Images: {len([r for r in results if r['image_file']])} files")
    print(f"✓ Test completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
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
