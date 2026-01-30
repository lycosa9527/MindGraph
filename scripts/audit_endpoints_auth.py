"""
Endpoint Authentication Audit Script
====================================

Audits all API endpoints to identify:
1. Endpoints without authentication (potential security issues)
2. Endpoints with optional authentication
3. Endpoints that should require authentication but don't

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
import ast
import logging
import os
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Expected public endpoints (no auth required)
PUBLIC_ENDPOINTS = {
    # Health checks
    "/health",
    "/health/redis",
    "/health/database",
    "/health/all",
    "/health/processes",
    "/status",
    
    # Auth endpoints
    "/api/auth/login",
    "/api/auth/sms/login",
    "/api/auth/register",
    "/api/auth/register_sms",
    "/api/auth/sms/send",
    "/api/auth/sms/verify",
    "/api/auth/sms/send-login",
    "/api/auth/sms/send-reset",
    "/api/auth/sms/send-register",
    "/api/auth/reset-password",
    "/api/auth/captcha/generate",
    "/api/auth/phone/send-code",
    "/api/auth/mode",
    "/api/auth/organizations",
    "/loginByXz",
    "/favicon.ico",
    "/favicon.svg",
    
    # Public dashboard (has session verification)
    "/api/public/stats",
    "/api/public/map-data",
    "/api/public/activity-history",
    "/api/public/activity-stream",
    
    # Config
    "/config/features",
    
    # Demo/Public verification
    "/api/auth/demo/verify",
    "/api/auth/public-dashboard/verify",
}

# Endpoints that can have optional auth (acceptable)
OPTIONAL_AUTH_ENDPOINTS = {
    "/api/library/documents",  # List documents - public browsing
    "/api/library/documents/{document_id}/cover",  # Cover images - public
    "/api/askonce/health",  # Health check
    "/api/askonce/models",  # Model list - public info
}

# Endpoints that accept API keys (acceptable alternative to user auth)
API_KEY_ENDPOINTS = {
    "/api/llm/generate_multi_parallel",
    "/api/llm/generate_multi_progressive",
    "/api/png/export_png",
    "/api/png/generate_png",
    "/api/png/generate_dingtalk",
    "/api/layout/recalculate_mindmap_layout",
    "/api/diagram/generate_graph",
    "/api/ai_assistant/stream",
    "/api/dify/files/upload",
    "/api/dify/app/parameters",
    "/api/tab_suggestions",
    "/api/tab_expand",
}

# Endpoints that should be public (frontend utilities)
FRONTEND_UTILITY_ENDPOINTS = {
    "/api/frontend_log",
    "/api/frontend_log_batch",
    "/api/feedback",
    "/api/proxy-image",
    "/api/png/temp_images/{filepath:path}",
}

# DebateVerse endpoints with optional auth (public feature)
DEBATEVERSE_OPTIONAL_AUTH = {
    "/api/debateverse/sessions",
    "/api/debateverse/sessions/{session_id}",
    "/api/debateverse/sessions/{session_id}/coin-toss",
    "/api/debateverse/sessions/{session_id}/generate-positions",
    "/api/debateverse/sessions/{session_id}/advance-stage",
    "/api/debateverse/sessions/{session_id}/messages",
    "/api/debateverse/next",
    "/api/debateverse/sessions/{session_id}/stream/{participant_id}",
}

ALL_ACCEPTABLE_PUBLIC = (
    PUBLIC_ENDPOINTS |
    OPTIONAL_AUTH_ENDPOINTS |
    API_KEY_ENDPOINTS |
    FRONTEND_UTILITY_ENDPOINTS |
    DEBATEVERSE_OPTIONAL_AUTH
)


class EndpointAuditor:
    """Audits FastAPI router files for authentication requirements."""
    
    def __init__(self, routers_dir: Path):
        self.routers_dir = routers_dir
        self.endpoints: Dict[str, Dict] = defaultdict(dict)
        self.auth_patterns = {
            'required': [
                'get_current_user',
                'require_admin',
                'require_manager',
                'require_admin_or_manager',
            ],
            'optional': [
                'get_current_user_optional',
                'get_optional_user',
            ],
            'api_key': [
                'get_current_user_or_api_key',
            ],
        }
    
    def find_router_files(self) -> List[Path]:
        """Find all Python router files."""
        router_files = []
        for py_file in self.routers_dir.rglob("*.py"):
            # Skip __init__ and test files
            if py_file.name.startswith("__") or "test" in py_file.name.lower():
                continue
            router_files.append(py_file)
        return sorted(router_files)
    
    def parse_endpoint(self, node: ast.FunctionDef, decorators: List[ast.Call]) -> Tuple[str, str, Dict]:
        """Parse an endpoint function to extract route info."""
        route_method = None
        route_path = None
        
        for decorator in decorators:
            if isinstance(decorator, ast.Call):
                if isinstance(decorator.func, ast.Attribute):
                    if decorator.func.attr in ['get', 'post', 'put', 'delete', 'patch', 'head']:
                        route_method = decorator.func.attr.upper()
                        # Extract path from first argument
                        if decorator.args:
                            if isinstance(decorator.args[0], ast.Constant):
                                route_path = decorator.args[0].value
                            elif isinstance(decorator.args[0], ast.Str):  # Python < 3.8
                                route_path = decorator.args[0].s
        
        if not route_method or not route_path:
            return None, None, {}
        
        # Check function parameters for auth dependencies
        auth_type = None
        has_auth = False
        
        for arg in node.args.args:
            if arg.annotation:
                # Check if it's a Depends() call
                if isinstance(arg.annotation, ast.Call):
                    if isinstance(arg.annotation.func, ast.Name):
                        if arg.annotation.func.id == 'Depends':
                            # Check what's inside Depends()
                            if arg.annotation.args:
                                dep_target = arg.annotation.args[0]
                                if isinstance(dep_target, ast.Name):
                                    dep_name = dep_target.id
                                    for auth_cat, patterns in self.auth_patterns.items():
                                        if any(pattern in dep_name for pattern in patterns):
                                            auth_type = auth_cat
                                            has_auth = True
                                            break
                                elif isinstance(dep_target, ast.Attribute):
                                    dep_name = dep_target.attr
                                    for auth_cat, patterns in self.auth_patterns.items():
                                        if any(pattern in dep_name for pattern in patterns):
                                            auth_type = auth_cat
                                            has_auth = True
                                            break
        
        # Check decorator dependencies
        for decorator in decorators:
            if isinstance(decorator, ast.Call):
                if isinstance(decorator.func, ast.Name) and decorator.func.id == 'Depends':
                    if decorator.args:
                        dep_target = decorator.args[0]
                        if isinstance(dep_target, ast.Name):
                            dep_name = dep_target.id
                            if 'require_admin' in dep_name or 'get_current_user' in dep_name:
                                auth_type = 'required'
                                has_auth = True
        
        return route_method, route_path, {
            'has_auth': has_auth,
            'auth_type': auth_type,
            'function': node.name,
        }
    
    def audit_file(self, file_path: Path) -> List[Dict]:
        """Audit a single router file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content, filename=str(file_path))
            endpoints = []
            
            # Find router prefix
            router_prefix = None
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id == 'router':
                            if isinstance(node.value, ast.Call):
                                if isinstance(node.value.func, ast.Name) and node.value.func.id == 'APIRouter':
                                    # Check for prefix argument
                                    for keyword in node.value.keywords:
                                        if keyword.arg == 'prefix':
                                            if isinstance(keyword.value, ast.Constant):
                                                router_prefix = keyword.value.value
                                            elif isinstance(keyword.value, ast.Str):
                                                router_prefix = keyword.value.s
            
            # Find all route decorators
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    decorators = []
                    for decorator in node.decorator_list:
                        if isinstance(decorator, ast.Call):
                            decorators.append(decorator)
                        elif isinstance(decorator, ast.Attribute):
                            # Handle @router.get style
                            decorators.append(decorator)
                    
                    method, path, info = self.parse_endpoint(node, decorators)
                    if method and path:
                        full_path = f"{router_prefix}{path}" if router_prefix else path
                        endpoints.append({
                            'method': method,
                            'path': full_path,
                            'file': str(file_path.relative_to(self.routers_dir)),
                            'function': info.get('function'),
                            'has_auth': info.get('has_auth', False),
                            'auth_type': info.get('auth_type'),
                        })
            
            return endpoints
        
        except Exception as e:
            logger.warning(f"Error parsing {file_path}: {e}")
            return []
    
    def audit_all(self) -> Dict[str, List[Dict]]:
        """Audit all router files."""
        router_files = self.find_router_files()
        all_endpoints = []
        
        for router_file in router_files:
            endpoints = self.audit_file(router_file)
            all_endpoints.extend(endpoints)
        
        # Categorize endpoints
        categorized = {
            'no_auth': [],
            'optional_auth': [],
            'api_key_auth': [],
            'required_auth': [],
            'unknown': [],
        }
        
        for endpoint in all_endpoints:
            path = endpoint['path']
            
            if endpoint['has_auth']:
                if endpoint['auth_type'] == 'required':
                    categorized['required_auth'].append(endpoint)
                elif endpoint['auth_type'] == 'optional':
                    categorized['optional_auth'].append(endpoint)
                elif endpoint['auth_type'] == 'api_key':
                    categorized['api_key_auth'].append(endpoint)
                else:
                    categorized['unknown'].append(endpoint)
            else:
                categorized['no_auth'].append(endpoint)
        
        return categorized
    
    def generate_report(self, categorized: Dict[str, List[Dict]]) -> str:
        """Generate audit report."""
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("ENDPOINT AUTHENTICATION AUDIT REPORT")
        report_lines.append("=" * 80)
        report_lines.append("")
        
        # Summary
        total = sum(len(endpoints) for endpoints in categorized.values())
        report_lines.append("SUMMARY:")
        report_lines.append(f"  Total endpoints found: {total}")
        report_lines.append(f"  Required auth: {len(categorized['required_auth'])}")
        report_lines.append(f"  Optional auth: {len(categorized['optional_auth'])}")
        report_lines.append(f"  API key auth: {len(categorized['api_key_auth'])}")
        report_lines.append(f"  No auth: {len(categorized['no_auth'])}")
        report_lines.append("")
        
        # Endpoints without auth that should have it
        report_lines.append("=" * 80)
        report_lines.append("POTENTIAL SECURITY ISSUES: Endpoints without authentication")
        report_lines.append("=" * 80)
        report_lines.append("")
        
        issues = []
        for endpoint in categorized['no_auth']:
            path = endpoint['path']
            # Check if it's in acceptable public list
            is_acceptable = False
            for acceptable in ALL_ACCEPTABLE_PUBLIC:
                if acceptable == path or (
                    '{' in acceptable and path.startswith(acceptable.split('{')[0])
                ):
                    is_acceptable = True
                    break
            
            if not is_acceptable:
                issues.append(endpoint)
        
        if issues:
            report_lines.append(f"Found {len(issues)} endpoints that may need authentication:")
            report_lines.append("")
            for endpoint in sorted(issues, key=lambda x: x['path']):
                report_lines.append(f"  {endpoint['method']:6} {endpoint['path']:60} ({endpoint['file']})")
        else:
            report_lines.append("[OK] No security issues found!")
        
        report_lines.append("")
        report_lines.append("=" * 80)
        report_lines.append("ENDPOINTS WITH OPTIONAL AUTHENTICATION")
        report_lines.append("=" * 80)
        report_lines.append("")
        
        if categorized['optional_auth']:
            for endpoint in sorted(categorized['optional_auth'], key=lambda x: x['path']):
                report_lines.append(f"  {endpoint['method']:6} {endpoint['path']:60} ({endpoint['file']})")
        else:
            report_lines.append("  None")
        
        report_lines.append("")
        report_lines.append("=" * 80)
        report_lines.append("ENDPOINTS WITH API KEY AUTHENTICATION")
        report_lines.append("=" * 80)
        report_lines.append("")
        
        if categorized['api_key_auth']:
            for endpoint in sorted(categorized['api_key_auth'], key=lambda x: x['path']):
                report_lines.append(f"  {endpoint['method']:6} {endpoint['path']:60} ({endpoint['file']})")
        else:
            report_lines.append("  None")
        
        report_lines.append("")
        report_lines.append("=" * 80)
        report_lines.append("ALL ENDPOINTS WITHOUT AUTHENTICATION")
        report_lines.append("=" * 80)
        report_lines.append("")
        
        if categorized['no_auth']:
            for endpoint in sorted(categorized['no_auth'], key=lambda x: x['path']):
                acceptable = "[OK]" if any(
                    acceptable == endpoint['path'] or (
                        '{' in acceptable and endpoint['path'].startswith(acceptable.split('{')[0])
                    )
                    for acceptable in ALL_ACCEPTABLE_PUBLIC
                ) else "[WARN]"
                report_lines.append(
                    f"  {acceptable} {endpoint['method']:6} {endpoint['path']:60} ({endpoint['file']})"
                )
        else:
            report_lines.append("  None")
        
        return "\n".join(report_lines)


def main():
    """Main entry point."""
    project_root = Path(__file__).parent.parent
    routers_dir = project_root / "routers"
    
    if not routers_dir.exists():
        logger.error(f"Routers directory not found: {routers_dir}")
        return
    
    auditor = EndpointAuditor(routers_dir)
    categorized = auditor.audit_all()
    report = auditor.generate_report(categorized)
    
    print(report)
    
    # Save report to file
    report_file = project_root / "endpoint_auth_audit_report.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    logger.info(f"Report saved to: {report_file}")


if __name__ == "__main__":
    main()
