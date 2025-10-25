#!/usr/bin/env python3
"""
Demo Mode Configuration Verification Script
Author: lycosa9527
Made by: MindSpring Team

This script verifies that your demo mode configuration is correct
and helps diagnose common issues with passkey authentication.
"""

import os
import sys
from pathlib import Path

def print_header(text):
    """Print a formatted header"""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)

def print_status(ok, message):
    """Print a status message with checkmark or cross"""
    symbol = "✓" if ok else "✗"
    color = "\033[92m" if ok else "\033[91m"  # Green or Red
    reset = "\033[0m"
    print(f"{color}{symbol}{reset} {message}")

def check_env_file():
    """Check if .env file exists and is readable"""
    print_header("1. Checking .env File")
    
    env_path = Path('.env')
    
    if not env_path.exists():
        print_status(False, ".env file not found!")
        print("  → Create .env file: cp env.example .env")
        return False
    
    print_status(True, ".env file exists")
    
    if not env_path.is_file():
        print_status(False, ".env is not a file!")
        return False
    
    print_status(True, ".env is a regular file")
    
    if not os.access(env_path, os.R_OK):
        print_status(False, ".env is not readable!")
        print(f"  → Fix permissions: chmod 644 .env")
        return False
    
    print_status(True, ".env is readable")
    
    return True

def check_whitespace(key, value):
    """Check if a value has whitespace issues"""
    if value is None:
        return False, "NOT SET"
    
    if value != value.strip():
        if value.startswith(' ') or value.startswith('\t'):
            return False, "HAS LEADING WHITESPACE"
        if value.endswith(' ') or value.endswith('\t'):
            return False, "HAS TRAILING WHITESPACE"
        return False, "HAS WHITESPACE"
    
    return True, "OK"

def check_environment_vars():
    """Check environment variables"""
    print_header("2. Checking Environment Variables")
    
    # Try to load dotenv
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print_status(True, "python-dotenv loaded successfully")
    except ImportError:
        print_status(False, "python-dotenv not installed!")
        print("  → Install: pip3 install python-dotenv")
        return False
    
    # Check required variables
    checks = {
        'AUTH_MODE': os.getenv('AUTH_MODE'),
        'DEMO_PASSKEY': os.getenv('DEMO_PASSKEY'),
        'ADMIN_DEMO_PASSKEY': os.getenv('ADMIN_DEMO_PASSKEY')
    }
    
    all_ok = True
    
    for key, value in checks.items():
        print(f"\n{key}:")
        
        if value is None:
            print_status(False, f"  Not set in .env file")
            all_ok = False
            continue
        
        # Check value
        print(f"  Value: '{value}'")
        print(f"  Length: {len(value)} characters")
        
        # Check for whitespace
        ws_ok, ws_msg = check_whitespace(key, value)
        print_status(ws_ok, f"  Whitespace check: {ws_msg}")
        
        if not ws_ok:
            all_ok = False
            print(f"  → Raw repr: {repr(value)}")
            print(f"  → Should be: '{value.strip()}'")
    
    return all_ok

def check_auth_mode():
    """Check AUTH_MODE setting"""
    print_header("3. Checking AUTH_MODE Setting")
    
    auth_mode = os.getenv('AUTH_MODE', '').strip().lower()
    
    if not auth_mode:
        print_status(False, "AUTH_MODE not set!")
        print("  → Add to .env: AUTH_MODE=demo")
        return False
    
    print(f"AUTH_MODE: '{auth_mode}'")
    
    if auth_mode == 'demo':
        print_status(True, "AUTH_MODE is set to 'demo'")
        return True
    else:
        print_status(False, f"AUTH_MODE is '{auth_mode}', not 'demo'!")
        print("  → Change in .env: AUTH_MODE=demo")
        return False

def check_passkey_format():
    """Check passkey format and strength"""
    print_header("4. Checking Passkey Format")
    
    demo_passkey = os.getenv('DEMO_PASSKEY', '').strip()
    admin_passkey = os.getenv('ADMIN_DEMO_PASSKEY', '').strip()
    
    all_ok = True
    
    print("\nDEMO_PASSKEY:")
    if not demo_passkey:
        print_status(False, "  Not set!")
        all_ok = False
    else:
        print_status(True, f"  Set: '{demo_passkey}' ({len(demo_passkey)} chars)")
        
        if len(demo_passkey) < 6:
            print_status(False, f"  Too short! Use at least 6 characters")
            all_ok = False
        else:
            print_status(True, f"  Length OK")
    
    print("\nADMIN_DEMO_PASSKEY:")
    if not admin_passkey:
        print_status(False, "  Not set!")
        all_ok = False
    else:
        print_status(True, f"  Set: '{admin_passkey}' ({len(admin_passkey)} chars)")
        
        if len(admin_passkey) < 6:
            print_status(False, f"  Too short! Use at least 6 characters")
            all_ok = False
        else:
            print_status(True, f"  Length OK")
        
        if demo_passkey == admin_passkey:
            print_status(False, "  WARNING: Same as DEMO_PASSKEY!")
            print("  → Use different passkeys for security")
    
    return all_ok

def test_passkey_verification():
    """Test the passkey verification function"""
    print_header("5. Testing Passkey Verification")
    
    try:
        # Import after dotenv is loaded
        from utils.auth import verify_demo_passkey, DEMO_PASSKEY, ADMIN_DEMO_PASSKEY
        
        demo_key = DEMO_PASSKEY
        admin_key = ADMIN_DEMO_PASSKEY
        
        print(f"\nExpected DEMO_PASSKEY: '{demo_key}' ({len(demo_key)} chars)")
        print(f"Expected ADMIN_DEMO_PASSKEY: '{admin_key}' ({len(admin_key)} chars)")
        
        # Test demo passkey
        print("\nTesting DEMO_PASSKEY verification:")
        if verify_demo_passkey(demo_key):
            print_status(True, f"  '{demo_key}' verified successfully")
        else:
            print_status(False, f"  '{demo_key}' verification FAILED!")
            return False
        
        # Test admin passkey
        print("\nTesting ADMIN_DEMO_PASSKEY verification:")
        if verify_demo_passkey(admin_key):
            print_status(True, f"  '{admin_key}' verified successfully")
        else:
            print_status(False, f"  '{admin_key}' verification FAILED!")
            return False
        
        # Test invalid passkey
        print("\nTesting invalid passkey:")
        if not verify_demo_passkey("000000"):
            print_status(True, "  Invalid passkey correctly rejected")
        else:
            print_status(False, "  Invalid passkey was accepted!")
            return False
        
        # Test whitespace handling
        print("\nTesting whitespace handling:")
        if verify_demo_passkey(f"  {demo_key}  "):
            print_status(True, "  Whitespace correctly stripped")
        else:
            print_status(False, "  Whitespace handling FAILED!")
            return False
        
        return True
        
    except Exception as e:
        print_status(False, f"  Error during verification: {e}")
        import traceback
        traceback.print_exc()
        return False

def print_summary(results):
    """Print final summary"""
    print_header("Summary")
    
    all_passed = all(results.values())
    
    for check, passed in results.items():
        print_status(passed, check)
    
    print("\n" + "=" * 70)
    if all_passed:
        print("✓ ALL CHECKS PASSED!")
        print("\nYour demo mode configuration is correct.")
        print("You can now start the server and use demo mode.")
    else:
        print("✗ SOME CHECKS FAILED!")
        print("\nPlease fix the issues above and run this script again.")
        print("\nQuick fixes:")
        print("  1. Ensure AUTH_MODE=demo in .env file")
        print("  2. Remove any whitespace from passkey values")
        print("  3. Restart the server after changes")
    print("=" * 70)
    
    return all_passed

def main():
    """Main verification routine"""
    print("\n" + "=" * 70)
    print("  Demo Mode Configuration Verification")
    print("  MindGraph by MindSpring Team")
    print("=" * 70)
    
    # Change to script's parent directory (project root)
    script_dir = Path(__file__).parent.parent
    os.chdir(script_dir)
    print(f"\nWorking directory: {os.getcwd()}\n")
    
    # Run checks
    results = {
        ".env file exists and is readable": check_env_file(),
        "Environment variables loaded correctly": check_environment_vars(),
        "AUTH_MODE is set to 'demo'": check_auth_mode(),
        "Passkeys have valid format": check_passkey_format(),
        "Passkey verification works": test_passkey_verification()
    }
    
    # Print summary
    all_passed = print_summary(results)
    
    # Exit with appropriate code
    sys.exit(0 if all_passed else 1)

if __name__ == "__main__":
    main()

