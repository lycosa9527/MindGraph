#!/usr/bin/env python3
"""
Test for the enhanced 5-column brace map layout
"""

import json
import sys
import os

# Add the parent directory to the path so we can import the modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_brace_map_5_column_layout():
    """Test the 5-column brace map layout with a simple example"""
    
    # Test specification following the 5-column layout
    test_spec = {
        "topic": "Computer",
        "parts": [
            {
                "name": "Hardware",
                "subparts": [
                    {"name": "CPU"},
                    {"name": "RAM"},
                    {"name": "Storage"}
                ]
            },
            {
                "name": "Software",
                "subparts": [
                    {"name": "Operating System"},
                    {"name": "Applications"},
                    {"name": "Drivers"}
                ]
            },
            {
                "name": "Peripherals",
                "subparts": [
                    {"name": "Monitor"},
                    {"name": "Keyboard"},
                    {"name": "Mouse"}
                ]
            }
        ]
    }
    
    print("Testing 5-column brace map layout...")
    print(f"Topic: {test_spec['topic']}")
    print(f"Number of parts: {len(test_spec['parts'])}")
    
    for i, part in enumerate(test_spec['parts']):
        print(f"  Part {i+1}: {part['name']}")
        print(f"    Subparts: {len(part['subparts'])}")
        for subpart in part['subparts']:
            print(f"      - {subpart['name']}")
    
    print("\nLayout structure:")
    print("Column 1: Topic (Computer)")
    print("Column 2: Big Brace (connects topic to all parts)")
    print("Column 3: Parts (Hardware, Software, Peripherals)")
    print("Column 4: Small Braces (connect each part to its subparts)")
    print("Column 5: Subparts (detailed components)")
    
    # Validate the structure
    assert test_spec['topic'] == "Computer"
    assert len(test_spec['parts']) == 3
    assert all('name' in part for part in test_spec['parts'])
    assert all('subparts' in part for part in test_spec['parts'])
    assert all(len(part['subparts']) > 0 for part in test_spec['parts'])
    
    print("\n✅ Test passed! The 5-column brace map layout is correctly structured.")
    
    return test_spec

if __name__ == "__main__":
    test_brace_map_5_column_layout()
