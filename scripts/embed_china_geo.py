#!/usr/bin/env python3
"""
Embed China GeoJSON into public-dashboard.js
===========================================

Reads china-geo.json and embeds it as a JavaScript constant in public-dashboard.js
to eliminate the need for a separate HTTP request.
"""

import json
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
CHINA_GEO_PATH = BASE_DIR / "static" / "data" / "china-geo.json"
PUBLIC_DASHBOARD_JS = BASE_DIR / "static" / "js" / "public-dashboard.js"

def embed_china_geo():
    """Embed china-geo.json into public-dashboard.js."""
    # Read the geoJSON file
    if not CHINA_GEO_PATH.exists():
        print(f"Error: {CHINA_GEO_PATH} not found")
        print("Please run: python scripts/download_dashboard_dependencies.py")
        return False

    with open(CHINA_GEO_PATH, 'r', encoding='utf-8') as f:
        geo_data = json.load(f)

    # Convert to JavaScript string (minified JSON)
    geo_json_str = json.dumps(geo_data, ensure_ascii=False, separators=(',', ':'))

    # Read the current JavaScript file
    with open(PUBLIC_DASHBOARD_JS, 'r', encoding='utf-8') as f:
        js_content = f.read()

    # Find and replace the chinaGeoJSON initialization
    # Replace: let chinaGeoJSON = null;
    # With: const chinaGeoJSON = <embedded_data>;

    old_declaration = "let chinaGeoJSON = null;"
    new_declaration = f"const chinaGeoJSON = {geo_json_str};"

    if old_declaration in js_content:
        js_content = js_content.replace(old_declaration, new_declaration)
    else:
        # Try alternative format
        old_declaration = "var chinaGeoJSON = null;"
        new_declaration = f"const chinaGeoJSON = {geo_json_str};"
        if old_declaration in js_content:
            js_content = js_content.replace(old_declaration, new_declaration)
        else:
            print("Warning: Could not find chinaGeoJSON declaration to replace")
            # Try to insert after the first few lines
            lines = js_content.split('\n')
            for i, line in enumerate(lines):
                if 'chinaGeoJSON' in line and 'null' in line:
                    lines[i] = new_declaration
                    js_content = '\n'.join(lines)
                    break

    # Remove the loadChinaGeoJSON function and its call
    # Find the function definition
    if 'async function loadChinaGeoJSON()' in js_content:
        # Find the function start
        func_start = js_content.find('async function loadChinaGeoJSON()')
        # Find the function end (next closing brace at same indentation level)
        func_lines = js_content[func_start:].split('\n')
        brace_count = 0
        func_end = func_start
        in_function = False
        for i, line in enumerate(func_lines):
            if 'async function loadChinaGeoJSON()' in line:
                in_function = True
            if in_function:
                brace_count += line.count('{') - line.count('}')
                if brace_count == 0 and i > 0:
                    func_end = func_start + len('\n'.join(func_lines[:i+1]))
                    break

        if func_end > func_start:
            # Remove the function
            js_content = js_content[:func_start] + js_content[func_end+1:]

    # Remove calls to loadChinaGeoJSON()
    js_content = js_content.replace('await loadChinaGeoJSON();', '')
    js_content = js_content.replace('loadChinaGeoJSON();', '')

    # Write the updated file
    with open(PUBLIC_DASHBOARD_JS, 'w', encoding='utf-8') as f:
        f.write(js_content)

    print(f"Successfully embedded china-geo.json into {PUBLIC_DASHBOARD_JS.name}")
    print(f"File size: {len(geo_json_str):,} characters")
    return True

if __name__ == "__main__":
    embed_china_geo()

