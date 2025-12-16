"""
Error Handling Verification Script
===================================

Verifies error parsers can handle real-world error messages from server logs.
Tests actual error scenarios and confirms proper exception types and user messages.

Run: python tests/verify_error_handling.py
or: python -m pytest tests/verify_error_handling.py -v

@author lycosa9527
@made_by MindSpring Team
"""

import json
import sys
import os
import importlib.util

# Add project root to path (parent directory of tests folder)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Load modules directly without triggering __init__.py
def load_module(file_path):
    """Load a module directly from file path"""
    spec = importlib.util.spec_from_file_location(os.path.basename(file_path), file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

# Load error_handler directly
error_handler = load_module(os.path.join(project_root, "services", "error_handler.py"))
dashscope_parser = load_module(os.path.join(project_root, "services", "dashscope_error_parser.py"))
hunyuan_parser = load_module(os.path.join(project_root, "services", "hunyuan_error_parser.py"))

# Import what we need
LLMInvalidParameterError = error_handler.LLMInvalidParameterError
LLMQuotaExhaustedError = error_handler.LLMQuotaExhaustedError
LLMModelNotFoundError = error_handler.LLMModelNotFoundError
LLMAccessDeniedError = error_handler.LLMAccessDeniedError
LLMContentFilterError = error_handler.LLMContentFilterError
LLMRateLimitError = error_handler.LLMRateLimitError
LLMTimeoutError = error_handler.LLMTimeoutError
LLMServiceError = error_handler.LLMServiceError
LLMProviderError = error_handler.LLMProviderError

parse_dashscope_error = dashscope_parser.parse_dashscope_error
parse_hunyuan_error = hunyuan_parser.parse_hunyuan_error


def test_case(name, test_func):
    """Run a test case and report results"""
    try:
        test_func()
        print(f"[PASS] {name}")
        return True
    except AssertionError as e:
        print(f"[FAIL] {name}: {e}")
        return False
    except Exception as e:
        print(f"[FAIL] {name}: Unexpected error - {e}")
        import traceback
        traceback.print_exc()
        return False


def test_dashscope_errors():
    """Test DashScope error parsing with real-world errors"""
    print("\n" + "="*70)
    print("Testing DashScope Error Parser")
    print("="*70)
    
    passed = 0
    total = 0
    
    # Test 1: Invalid parameter - enable_thinking
    total += 1
    def test_enable_thinking():
        error_text = json.dumps({
            "error": {
                "code": "InvalidParameter",
                "message": "parameter.enable_thinking must be set to false for non-streaming calls"
            }
        })
        exception, _ = parse_dashscope_error(400, error_text)
        assert type(exception).__name__ == 'LLMInvalidParameterError', f"Expected LLMInvalidParameterError, got {type(exception).__name__}"
        assert exception.parameter == 'enable_thinking', f"Expected parameter='enable_thinking', got {exception.parameter}"
        assert exception.provider == 'dashscope', f"Expected provider='dashscope', got {exception.provider}"
    
    if test_case("400 Invalid Parameter (enable_thinking)", test_enable_thinking):
        passed += 1
    
    # Test 2: Input length exceeded
    total += 1
    def test_input_length():
        error_text = json.dumps({
            "error": {
                "code": "InvalidParameter",
                "message": "Range of input length should be [1, 200000]"
            }
        })
        exception, _ = parse_dashscope_error(400, error_text)
        assert type(exception).__name__ == 'LLMInvalidParameterError'
        assert exception.parameter == 'messages'
    
    if test_case("400 Input Length Exceeded", test_input_length):
        passed += 1
    
    # Test 3: Model not found
    total += 1
    def test_model_not_found():
        error_text = json.dumps({
            "error": {
                "code": "ModelNotFound",
                "message": "Model not exist."
            }
        })
        exception, _ = parse_dashscope_error(400, error_text)
        assert type(exception).__name__ == 'LLMModelNotFoundError'
        assert exception.provider == 'dashscope'
    
    if test_case("400 Model Not Found", test_model_not_found):
        passed += 1
    
    # Test 4: Invalid API key
    total += 1
    def test_invalid_api_key():
        error_text = json.dumps({
            "error": {
                "code": "InvalidApiKey",
                "message": "Invalid API-key provided."
            }
        })
        exception, _ = parse_dashscope_error(401, error_text)
        assert type(exception).__name__ == 'LLMAccessDeniedError'
        assert exception.provider == 'dashscope'
    
    if test_case("401 Invalid API Key", test_invalid_api_key):
        passed += 1
    
    # Test 5: Quota exhausted
    total += 1
    def test_quota_exhausted():
        error_text = json.dumps({
            "error": {
                "code": "AccessDenied.Quota",
                "message": "Allocated quota exceeded, please increase your quota limit."
            }
        })
        exception, _ = parse_dashscope_error(403, error_text)
        assert type(exception).__name__ == 'LLMQuotaExhaustedError'
        assert exception.provider == 'dashscope'
    
    if test_case("403 Quota Exhausted", test_quota_exhausted):
        passed += 1
    
    # Test 6: Rate limit
    total += 1
    def test_rate_limit():
        error_text = json.dumps({
            "error": {
                "code": "Throttling",
                "message": "Requests throttling triggered."
            }
        })
        exception, _ = parse_dashscope_error(429, error_text)
        assert type(exception).__name__ == 'LLMRateLimitError'
    
    if test_case("429 Rate Limit", test_rate_limit):
        passed += 1
    
    # Test 7: Timeout
    total += 1
    def test_timeout():
        error_text = json.dumps({
            "error": {
                "code": "RequestTimeOut",
                "message": "Request timed out, please try again later."
            }
        })
        exception, _ = parse_dashscope_error(500, error_text)
        assert type(exception).__name__ == 'LLMTimeoutError'
    
    if test_case("500 Timeout", test_timeout):
        passed += 1
    
    # Test 8: Content filter
    total += 1
    def test_content_filter():
        error_text = json.dumps({
            "error": {
                "code": "DataInspectionFailed",
                "message": "Input or output data may contain inappropriate content."
            }
        })
        exception, _ = parse_dashscope_error(400, error_text)
        assert type(exception).__name__ == 'LLMContentFilterError'
    
    if test_case("400 Content Filter", test_content_filter):
        passed += 1
    
    # Test 9: Malformed JSON (plain text error)
    total += 1
    def test_malformed_json():
        error_text = "Internal server error"
        exception, _ = parse_dashscope_error(500, error_text)
        assert type(exception).__name__ == 'LLMServiceError'
    
    if test_case("500 Malformed JSON Error", test_malformed_json):
        passed += 1
    
    print(f"\nDashScope Tests: {passed}/{total} passed")
    return passed, total


def test_hunyuan_errors():
    """Test Hunyuan error parsing with real-world errors"""
    print("\n" + "="*70)
    print("Testing Hunyuan Error Parser")
    print("="*70)
    
    passed = 0
    total = 0
    
    # Test 1: Invalid secret ID
    total += 1
    def test_invalid_secret_id():
        exception, _ = parse_hunyuan_error("AuthFailure.InvalidSecretId", "密钥非法")
        assert type(exception).__name__ == 'LLMAccessDeniedError'
        assert exception.provider == 'hunyuan'
        assert exception.error_code == "AuthFailure.InvalidSecretId"
    
    if test_case("AuthFailure.InvalidSecretId", test_invalid_secret_id):
        passed += 1
    
    # Test 2: Signature expired
    total += 1
    def test_signature_expire():
        exception, _ = parse_hunyuan_error("AuthFailure.SignatureExpire", "签名过期")
        assert type(exception).__name__ == 'LLMAccessDeniedError'
        assert exception.provider == 'hunyuan'
    
    if test_case("AuthFailure.SignatureExpire", test_signature_expire):
        passed += 1
    
    # Test 3: Invalid parameter
    total += 1
    def test_invalid_parameter():
        exception, _ = parse_hunyuan_error("InvalidParameter", "参数错误")
        assert type(exception).__name__ == 'LLMInvalidParameterError'
        assert exception.provider == 'hunyuan'
    
    if test_case("InvalidParameter", test_invalid_parameter):
        passed += 1
    
    # Test 4: Model not found
    total += 1
    def test_model_not_found_hunyuan():
        exception, _ = parse_hunyuan_error("InvalidParameterValue.Model", "模型不存在")
        assert type(exception).__name__ == 'LLMModelNotFoundError'
        assert exception.provider == 'hunyuan'
    
    if test_case("InvalidParameterValue.Model", test_model_not_found_hunyuan):
        passed += 1
    
    # Test 5: Rate limit
    total += 1
    def test_rate_limit_hunyuan():
        exception, _ = parse_hunyuan_error("RequestLimitExceeded", "请求的次数超过了频率限制")
        assert type(exception).__name__ == 'LLMRateLimitError'
    
    if test_case("RequestLimitExceeded", test_rate_limit_hunyuan):
        passed += 1
    
    # Test 6: Quota exhausted
    total += 1
    def test_quota_exhausted_hunyuan():
        exception, _ = parse_hunyuan_error("FailedOperation.ResourcePackExhausted", "资源包余量已用尽")
        assert type(exception).__name__ == 'LLMQuotaExhaustedError'
        assert exception.provider == 'hunyuan'
    
    if test_case("FailedOperation.ResourcePackExhausted", test_quota_exhausted_hunyuan):
        passed += 1
    
    # Test 7: Content filter
    total += 1
    def test_content_filter_hunyuan():
        exception, _ = parse_hunyuan_error("OperationDenied.TextIllegalDetected", "文本包含违法违规信息")
        assert type(exception).__name__ == 'LLMContentFilterError'
    
    if test_case("OperationDenied.TextIllegalDetected", test_content_filter_hunyuan):
        passed += 1
    
    # Test 8: Engine timeout
    total += 1
    def test_engine_timeout():
        exception, _ = parse_hunyuan_error("FailedOperation.EngineRequestTimeout", "引擎层请求超时")
        assert type(exception).__name__ == 'LLMTimeoutError'
    
    if test_case("FailedOperation.EngineRequestTimeout", test_engine_timeout):
        passed += 1
    
    # Test 9: Service not activated
    total += 1
    def test_service_not_activated():
        exception, _ = parse_hunyuan_error("FailedOperation.ServiceNotActivated", "服务未开通")
        assert type(exception).__name__ == 'LLMAccessDeniedError'
        assert exception.provider == 'hunyuan'
    
    if test_case("FailedOperation.ServiceNotActivated", test_service_not_activated):
        passed += 1
    
    # Test 10: Account in arrears
    total += 1
    def test_account_arrears():
        exception, _ = parse_hunyuan_error("ResourceUnavailable.InArrears", "账号已欠费")
        assert type(exception).__name__ == 'LLMQuotaExhaustedError'
        assert exception.provider == 'hunyuan'
    
    if test_case("ResourceUnavailable.InArrears", test_account_arrears):
        passed += 1
    
    print(f"\nHunyuan Tests: {passed}/{total} passed")
    return passed, total


def test_user_messages():
    """Test that user-friendly messages are generated"""
    print("\n" + "="*70)
    print("Testing User-Friendly Messages")
    print("="*70)
    
    passed = 0
    total = 0
    
    # Test DashScope user messages
    total += 1
    def test_dashscope_user_msg():
        error_text = json.dumps({
            "error": {
                "code": "InvalidApiKey",
                "message": "Invalid API-key provided."
            }
        })
        exception, user_msg = parse_dashscope_error(401, error_text)
        assert user_msg is not None
        assert len(user_msg) > 0
    
    if test_case("DashScope User Message Generated", test_dashscope_user_msg):
        passed += 1
    
    # Test Hunyuan user messages
    total += 1
    def test_hunyuan_user_msg():
        exception, user_msg = parse_hunyuan_error("AuthFailure.InvalidSecretId", "密钥非法")
        assert user_msg is not None
        assert len(user_msg) > 0
    
    if test_case("Hunyuan User Message Generated", test_hunyuan_user_msg):
        passed += 1
    
    # Test bilingual support
    total += 1
    def test_bilingual():
        error_text = json.dumps({
            "error": {
                "code": "InvalidParameter",
                "message": "参数错误"
            }
        })
        _, user_msg = parse_dashscope_error(400, error_text)
        # Should contain either Chinese or English
        assert ('参数' in user_msg or 'parameter' in user_msg.lower())
    
    if test_case("Bilingual Message Support", test_bilingual):
        passed += 1
    
    print(f"\nUser Message Tests: {passed}/{total} passed")
    return passed, total


def test_exception_attributes():
    """Test that exceptions have correct attributes"""
    print("\n" + "="*70)
    print("Testing Exception Attributes")
    print("="*70)
    
    passed = 0
    total = 0
    
    # Test DashScope exception attributes
    total += 1
    def test_dashscope_attributes():
        error_text = json.dumps({
            "error": {
                "code": "InvalidParameter",
                "message": "Invalid parameter"
            }
        })
        exception, _ = parse_dashscope_error(400, error_text)
        assert type(exception).__name__ == 'LLMInvalidParameterError'
        assert exception.provider == 'dashscope'
        assert exception.error_code is not None
    
    if test_case("DashScope Exception Has Provider", test_dashscope_attributes):
        passed += 1
    
    # Test Hunyuan exception attributes
    total += 1
    def test_hunyuan_attributes():
        exception, _ = parse_hunyuan_error("InvalidParameter", "参数错误")
        assert type(exception).__name__ == 'LLMInvalidParameterError'
        assert exception.provider == 'hunyuan'
        assert exception.error_code == 'InvalidParameter'
    
    if test_case("Hunyuan Exception Has Provider", test_hunyuan_attributes):
        passed += 1
    
    # Test parameter attribute
    total += 1
    def test_parameter_attribute():
        error_text = json.dumps({
            "error": {
                "code": "InvalidParameter",
                "message": "parameter.enable_thinking must be set to false"
            }
        })
        exception, _ = parse_dashscope_error(400, error_text)
        assert type(exception).__name__ == 'LLMInvalidParameterError'
        assert exception.parameter == 'enable_thinking'
    
    if test_case("Exception Has Parameter Attribute", test_parameter_attribute):
        passed += 1
    
    print(f"\nException Attribute Tests: {passed}/{total} passed")
    return passed, total


def main():
    """Run all verification tests"""
    print("\n" + "="*70)
    print("Error Handling Verification")
    print("Verifying error parsers can handle real-world server log errors")
    print("="*70)
    
    total_passed = 0
    total_tests = 0
    
    # Run all test suites
    passed, total = test_dashscope_errors()
    total_passed += passed
    total_tests += total
    
    passed, total = test_hunyuan_errors()
    total_passed += passed
    total_tests += total
    
    passed, total = test_user_messages()
    total_passed += passed
    total_tests += total
    
    passed, total = test_exception_attributes()
    total_passed += passed
    total_tests += total
    
    # Summary
    print("\n" + "="*70)
    print("VERIFICATION SUMMARY")
    print("="*70)
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {total_passed}")
    print(f"Failed: {total_tests - total_passed}")
    if total_tests > 0:
        print(f"Success Rate: {(total_passed/total_tests*100):.1f}%")
    print("="*70)
    
    if total_passed == total_tests:
        print("\n[SUCCESS] ALL TESTS PASSED - Error handling is ready for production!")
        return 0
    else:
        print(f"\n[WARNING] {total_tests - total_passed} TEST(S) FAILED - Review errors above")
        return 1


if __name__ == "__main__":
    sys.exit(main())
