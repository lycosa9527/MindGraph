#!/usr/bin/env python3
"""
MindGraph Waitress Server Launcher
Simple, clean server launcher using Waitress for cross-platform compatibility.
"""

import os
import sys
import platform
import subprocess
import importlib.util

def check_package_installed(package_name):
    """Check if a package is installed"""
    spec = importlib.util.find_spec(package_name)
    return spec is not None

def run_waitress():
    """Run MindGraph with Waitress"""
    if not check_package_installed('waitress'):
        print("Waitress not installed. Install with: pip install waitress>=3.0.0")
        sys.exit(1)
    
    try:
        # Ensure we're in the correct directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        os.chdir(script_dir)
        
        # Ensure logs directory exists
        os.makedirs("logs", exist_ok=True)
        
        from waitress import serve
        from app import app
        
        # Load configuration
        config_module = {}
        with open('waitress.conf.py', 'r') as f:
            exec(f.read(), config_module)
        
        # Display banner and user-friendly URL
        from app import print_banner
        display_host = "localhost" if config_module['host'] == '0.0.0.0' else config_module['host']
        print_banner(display_host, config_module['port'])
        print(f"Press Ctrl+C to stop the server")
        
        serve(
            app, 
            host=config_module['host'], 
            port=config_module['port'],
            threads=config_module['threads'],
            cleanup_interval=config_module['cleanup_interval'],
            channel_timeout=config_module['channel_timeout'],
            send_bytes=config_module['send_bytes'],
            recv_bytes=config_module['recv_bytes']
        )
    except Exception as e:
        print(f"Failed to start Waitress: {e}")
        sys.exit(1)

def run_flask_dev():
    """Fallback: Run Flask development server"""
    print("🟨 Starting MindGraph with Flask development server (fallback)")
    print("⚠️  WARNING: This is not recommended for production use")
    
    try:
        subprocess.run([sys.executable, 'app.py'])
    except Exception as e:
        print(f"Failed to start Flask development server: {e}")
        sys.exit(1)

def main():
    """Main entry point"""
    # Banner will be displayed by Waitress startup
    
    # Check if force mode is specified
    force_server = os.getenv('MINDGRAPH_SERVER', '').lower()
    
    if force_server == 'flask':
        run_flask_dev()
    else:
        # Default to Waitress
        run_waitress()

if __name__ == '__main__':
    main()
