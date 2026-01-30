"""
Simple Endpoint Authentication Audit Script
============================================

Uses regex to find all @router decorators and check for auth dependencies.
"""
import re
from collections import defaultdict
from pathlib import Path

# Expected public endpoints
PUBLIC_ENDPOINTS = {
    "/health", "/health/redis", "/health/database", "/health/all", "/health/processes", "/status",
    "/api/auth/login", "/api/auth/sms/login", "/api/auth/register", "/api/auth/register_sms",
    "/api/auth/sms/send", "/api/auth/sms/verify", "/api/auth/sms/send-login",
    "/api/auth/sms/send-reset", "/api/auth/sms/send-register", "/api/auth/reset-password",
    "/api/auth/captcha/generate", "/api/auth/phone/send-code", "/api/auth/mode",
    "/api/auth/organizations", "/loginByXz", "/favicon.ico", "/favicon.svg",
    "/api/public/stats", "/api/public/map-data", "/api/public/activity-history",
    "/api/public/activity-stream", "/config/features",
    "/api/auth/demo/verify", "/api/auth/public-dashboard/verify",
}

OPTIONAL_AUTH_ENDPOINTS = {
    "/api/library/documents", "/api/library/documents/{document_id}/cover",
    "/api/askonce/health", "/api/askonce/models",
}

API_KEY_ENDPOINTS = {
    "/api/llm/generate_multi_parallel", "/api/llm/generate_multi_progressive",
    "/api/png/export_png", "/api/png/generate_png", "/api/png/generate_dingtalk",
    "/api/layout/recalculate_mindmap_layout", "/api/diagram/generate_graph",
    "/api/ai_assistant/stream", "/api/dify/files/upload", "/api/dify/app/parameters",
    "/api/tab_suggestions", "/api/tab_expand",
}

FRONTEND_UTILITY = {
    "/api/frontend_log", "/api/frontend_log_batch", "/api/feedback",
    "/api/proxy-image", "/api/png/temp_images",
}

ALL_ACCEPTABLE = PUBLIC_ENDPOINTS | OPTIONAL_AUTH_ENDPOINTS | API_KEY_ENDPOINTS | FRONTEND_UTILITY


def find_endpoints_in_file(file_path: Path):
    """Find all endpoints in a router file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find router prefix
    prefix_match = re.search(r'router\s*=\s*APIRouter\([^)]*prefix\s*=\s*["\']([^"\']+)["\']', content)
    prefix = prefix_match.group(1) if prefix_match else ""
    
    # Find all @router.method decorators
    pattern = r'@router\.(get|post|put|delete|patch|head)\s*\(["\']([^"\']+)["\']'
    matches = re.finditer(pattern, content)
    
    endpoints = []
    for match in matches:
        method = match.group(1).upper()
        path = match.group(2)
        full_path = prefix + path
        
        # Find the function definition after this decorator
        start_pos = match.end()
        func_match = re.search(r'async\s+def\s+(\w+)', content[start_pos:start_pos+500])
        func_name = func_match.group(1) if func_match else "unknown"
        
        # Check for auth dependencies in function signature
        func_sig_match = re.search(
            r'async\s+def\s+\w+\s*\([^)]*\)',
            content[start_pos:start_pos+2000],
            re.DOTALL
        )
        has_auth = False
        auth_type = None
        
        if func_sig_match:
            func_sig = func_sig_match.group(0)
            
            # Check for required auth
            if re.search(r'get_current_user\s*=\s*Depends', func_sig):
                has_auth = True
                auth_type = 'required'
            elif re.search(r'require_admin\s*=\s*Depends', func_sig):
                has_auth = True
                auth_type = 'required'
            elif re.search(r'require_manager\s*=\s*Depends', func_sig):
                has_auth = True
                auth_type = 'required'
            elif re.search(r'require_admin_or_manager\s*=\s*Depends', func_sig):
                has_auth = True
                auth_type = 'required'
            # Check for optional auth
            elif re.search(r'get_current_user_optional\s*=\s*Depends', func_sig):
                has_auth = True
                auth_type = 'optional'
            elif re.search(r'get_optional_user\s*=\s*Depends', func_sig):
                has_auth = True
                auth_type = 'optional'
            # Check for API key auth
            elif re.search(r'get_current_user_or_api_key\s*=\s*Depends', func_sig):
                has_auth = True
                auth_type = 'api_key'
        
        # Check decorator dependencies
        deps_match = re.search(
            r'dependencies\s*=\s*\[.*?Depends\((get_current_user|require_admin)',
            content[start_pos:start_pos+500],
            re.DOTALL
        )
        if deps_match:
            has_auth = True
            auth_type = 'required'
        
        endpoints.append({
            'method': method,
            'path': full_path,
            'file': str(file_path.relative_to(Path('routers'))),
            'function': func_name,
            'has_auth': has_auth,
            'auth_type': auth_type,
        })
    
    return endpoints


def main():
    routers_dir = Path("routers")
    all_endpoints = []
    
    for py_file in routers_dir.rglob("*.py"):
        if py_file.name.startswith("__") or "test" in py_file.name.lower():
            continue
        endpoints = find_endpoints_in_file(py_file)
        all_endpoints.extend(endpoints)
    
    # Categorize
    no_auth = [e for e in all_endpoints if not e['has_auth']]
    required_auth = [e for e in all_endpoints if e.get('auth_type') == 'required']
    optional_auth = [e for e in all_endpoints if e.get('auth_type') == 'optional']
    api_key_auth = [e for e in all_endpoints if e.get('auth_type') == 'api_key']
    
    print("=" * 80)
    print("ENDPOINT AUTHENTICATION AUDIT REPORT")
    print("=" * 80)
    print(f"\nSUMMARY:")
    print(f"  Total endpoints: {len(all_endpoints)}")
    print(f"  Required auth: {len(required_auth)}")
    print(f"  Optional auth: {len(optional_auth)}")
    print(f"  API key auth: {len(api_key_auth)}")
    print(f"  No auth: {len(no_auth)}")
    
    # Check for issues
    print("\n" + "=" * 80)
    print("POTENTIAL SECURITY ISSUES: Endpoints without authentication")
    print("=" * 80)
    
    issues = []
    for endpoint in no_auth:
        path = endpoint['path']
        is_acceptable = False
        for acceptable in ALL_ACCEPTABLE:
            if acceptable == path:
                is_acceptable = True
                break
            # Handle path parameters
            if '{' in acceptable:
                prefix = acceptable.split('{')[0]
                if path.startswith(prefix):
                    is_acceptable = True
                    break
        
        if not is_acceptable:
            issues.append(endpoint)
    
    if issues:
        print(f"\nFound {len(issues)} endpoints that may need authentication:\n")
        for endpoint in sorted(issues, key=lambda x: x['path']):
            print(f"  {endpoint['method']:6} {endpoint['path']:60} ({endpoint['file']})")
    else:
        print("\n[OK] No security issues found!")
    
    print("\n" + "=" * 80)
    print("ALL ENDPOINTS WITHOUT AUTHENTICATION")
    print("=" * 80)
    if no_auth:
        for endpoint in sorted(no_auth, key=lambda x: x['path']):
            is_acceptable = any(
                acceptable == endpoint['path'] or (
                    '{' in acceptable and endpoint['path'].startswith(acceptable.split('{')[0])
                )
                for acceptable in ALL_ACCEPTABLE
            )
            status = "[OK]" if is_acceptable else "[WARN]"
            print(f"  {status} {endpoint['method']:6} {endpoint['path']:60} ({endpoint['file']})")
    else:
        print("  None")


if __name__ == "__main__":
    main()
