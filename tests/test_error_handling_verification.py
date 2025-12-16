"""
Error Handling Verification Test
=================================

Tests error parsers with real-world error messages that might appear in server logs.
Verifies that all error types are correctly identified and user-friendly messages are generated.

@author lycosa9527
@made_by MindSpring Team
"""

import pytest
import json
from services.dashscope_error_parser import parse_dashscope_error, parse_and_raise_dashscope_error
from services.hunyuan_error_parser import parse_hunyuan_error, parse_and_raise_hunyuan_error
from services.error_handler import (
    LLMInvalidParameterError,
    LLMQuotaExhaustedError,
    LLMModelNotFoundError,
    LLMAccessDeniedError,
    LLMContentFilterError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMServiceError,
    LLMProviderError
)


class TestDashScopeErrorParsing:
    """Test DashScope error parser with real-world error messages"""
    
    def test_400_invalid_parameter_enable_thinking(self):
        """Test enable_thinking parameter error"""
        error_text = json.dumps({
            "error": {
                "code": "InvalidParameter",
                "message": "parameter.enable_thinking must be set to false for non-streaming calls"
            }
        })
        
        exception, user_msg = parse_dashscope_error(400, error_text)
        assert isinstance(exception, LLMInvalidParameterError)
        assert exception.parameter == 'enable_thinking'
        assert exception.provider == 'dashscope'
        assert '思考模式' in user_msg or 'streaming' in user_msg.lower()
    
    def test_400_input_length_exceeded(self):
        """Test input length exceeded error"""
        error_text = json.dumps({
            "error": {
                "code": "InvalidParameter",
                "message": "Range of input length should be [1, 200000]"
            }
        })
        
        exception, user_msg = parse_dashscope_error(400, error_text)
        assert isinstance(exception, LLMInvalidParameterError)
        assert exception.parameter == 'messages'
        assert '输入内容过长' in user_msg or 'too long' in user_msg.lower()
    
    def test_400_model_not_found(self):
        """Test model not found error"""
        error_text = json.dumps({
            "error": {
                "code": "ModelNotFound",
                "message": "Model not exist."
            }
        })
        
        exception, user_msg = parse_dashscope_error(400, error_text)
        assert isinstance(exception, LLMModelNotFoundError)
        assert exception.provider == 'dashscope'
        assert '模型不存在' in user_msg or 'not found' in user_msg.lower()
    
    def test_401_invalid_api_key(self):
        """Test invalid API key error"""
        error_text = json.dumps({
            "error": {
                "code": "InvalidApiKey",
                "message": "Invalid API-key provided."
            }
        })
        
        exception, user_msg = parse_dashscope_error(401, error_text)
        assert isinstance(exception, LLMAccessDeniedError)
        assert exception.provider == 'dashscope'
        assert 'API密钥' in user_msg or 'api key' in user_msg.lower()
    
    def test_403_quota_exhausted(self):
        """Test quota exhausted error"""
        error_text = json.dumps({
            "error": {
                "code": "AccessDenied.Quota",
                "message": "Allocated quota exceeded, please increase your quota limit."
            }
        })
        
        exception, user_msg = parse_dashscope_error(403, error_text)
        assert isinstance(exception, LLMQuotaExhaustedError)
        assert exception.provider == 'dashscope'
        assert '配额' in user_msg or 'quota' in user_msg.lower()
    
    def test_429_rate_limit(self):
        """Test rate limit error"""
        error_text = json.dumps({
            "error": {
                "code": "Throttling",
                "message": "Requests throttling triggered."
            }
        })
        
        exception, user_msg = parse_dashscope_error(429, error_text)
        assert isinstance(exception, LLMRateLimitError)
        assert '请求过于频繁' in user_msg or 'rate limit' in user_msg.lower()
    
    def test_500_timeout(self):
        """Test timeout error"""
        error_text = json.dumps({
            "error": {
                "code": "RequestTimeOut",
                "message": "Request timed out, please try again later."
            }
        })
        
        exception, user_msg = parse_dashscope_error(500, error_text)
        assert isinstance(exception, LLMTimeoutError)
        assert '请求超时' in user_msg or 'timeout' in user_msg.lower()
    
    def test_content_filter_error(self):
        """Test content filter error"""
        error_text = json.dumps({
            "error": {
                "code": "DataInspectionFailed",
                "message": "Input or output data may contain inappropriate content."
            }
        })
        
        exception, user_msg = parse_dashscope_error(400, error_text)
        assert isinstance(exception, LLMContentFilterError)
        assert '不当信息' in user_msg or 'inappropriate' in user_msg.lower()
    
    def test_malformed_json_error(self):
        """Test handling of malformed JSON error response"""
        error_text = "Internal server error"
        
        exception, user_msg = parse_dashscope_error(500, error_text)
        assert isinstance(exception, LLMServiceError)
        assert '内部错误' in user_msg or 'internal' in user_msg.lower()
    
    def test_unknown_error_code(self):
        """Test unknown error code handling"""
        error_text = json.dumps({
            "error": {
                "code": "UnknownError",
                "message": "Something unexpected happened"
            }
        })
        
        exception, user_msg = parse_dashscope_error(500, error_text)
        assert isinstance(exception, LLMProviderError)
        assert exception.provider == 'dashscope'
        assert exception.error_code == 'UnknownError'


class TestHunyuanErrorParsing:
    """Test Hunyuan error parser with real-world error messages"""
    
    def test_auth_failure_invalid_secret_id(self):
        """Test invalid secret ID error"""
        error_code = "AuthFailure.InvalidSecretId"
        error_message = "密钥非法（不是云 API 密钥类型）"
        
        exception, user_msg = parse_hunyuan_error(error_code, error_message)
        assert isinstance(exception, LLMAccessDeniedError)
        assert exception.provider == 'hunyuan'
        assert exception.error_code == error_code
        assert '密钥类型错误' in user_msg or 'secret id' in user_msg.lower()
    
    def test_auth_failure_signature_expire(self):
        """Test signature expired error"""
        error_code = "AuthFailure.SignatureExpire"
        error_message = "签名过期。Timestamp 和服务器时间相差不得超过五分钟"
        
        exception, user_msg = parse_hunyuan_error(error_code, error_message)
        assert isinstance(exception, LLMAccessDeniedError)
        assert '签名已过期' in user_msg or 'signature expired' in user_msg.lower()
    
    def test_invalid_parameter(self):
        """Test invalid parameter error"""
        error_code = "InvalidParameter"
        error_message = "参数错误（包括参数格式、类型等错误）"
        
        exception, user_msg = parse_hunyuan_error(error_code, error_message)
        assert isinstance(exception, LLMInvalidParameterError)
        assert exception.provider == 'hunyuan'
        assert '参数错误' in user_msg or 'invalid parameter' in user_msg.lower()
    
    def test_invalid_parameter_value_model(self):
        """Test invalid model name error"""
        error_code = "InvalidParameterValue.Model"
        error_message = "模型不存在"
        
        exception, user_msg = parse_hunyuan_error(error_code, error_message)
        assert isinstance(exception, LLMModelNotFoundError)
        assert exception.provider == 'hunyuan'
        assert '模型不存在' in user_msg or 'model not found' in user_msg.lower()
    
    def test_rate_limit_exceeded(self):
        """Test rate limit error"""
        error_code = "RequestLimitExceeded"
        error_message = "请求的次数超过了频率限制"
        
        exception, user_msg = parse_hunyuan_error(error_code, error_message)
        assert isinstance(exception, LLMRateLimitError)
        assert '请求频率超过限制' in user_msg or 'rate limit' in user_msg.lower()
    
    def test_quota_exhausted(self):
        """Test quota exhausted error"""
        error_code = "FailedOperation.ResourcePackExhausted"
        error_message = "资源包余量已用尽，请购买资源包或开通后付费"
        
        exception, user_msg = parse_hunyuan_error(error_code, error_message)
        assert isinstance(exception, LLMQuotaExhaustedError)
        assert exception.provider == 'hunyuan'
        assert '资源包余量已用尽' in user_msg or 'resource pack' in user_msg.lower()
    
    def test_content_filter_text_illegal(self):
        """Test content filter error"""
        error_code = "OperationDenied.TextIllegalDetected"
        error_message = "文本包含违法违规信息，审核不通过"
        
        exception, user_msg = parse_hunyuan_error(error_code, error_message)
        assert isinstance(exception, LLMContentFilterError)
        assert '文本包含违法违规信息' in user_msg or 'illegal content' in user_msg.lower()
    
    def test_engine_timeout(self):
        """Test engine timeout error"""
        error_code = "FailedOperation.EngineRequestTimeout"
        error_message = "引擎层请求超时；请稍后重试"
        
        exception, user_msg = parse_hunyuan_error(error_code, error_message)
        assert isinstance(exception, LLMTimeoutError)
        assert '引擎层请求超时' in user_msg or 'timeout' in user_msg.lower()
    
    def test_service_not_activated(self):
        """Test service not activated error"""
        error_code = "FailedOperation.ServiceNotActivated"
        error_message = "服务未开通，请前往控制台申请试用"
        
        exception, user_msg = parse_hunyuan_error(error_code, error_message)
        assert isinstance(exception, LLMAccessDeniedError)
        assert exception.provider == 'hunyuan'
        assert '服务未开通' in user_msg or 'not activated' in user_msg.lower()
    
    def test_resource_unavailable_in_arrears(self):
        """Test account in arrears error"""
        error_code = "ResourceUnavailable.InArrears"
        error_message = "账号已欠费"
        
        exception, user_msg = parse_hunyuan_error(error_code, error_message)
        assert isinstance(exception, LLMQuotaExhaustedError)
        assert exception.provider == 'hunyuan'
        assert '账号已欠费' in user_msg or 'arrears' in user_msg.lower()
    
    def test_unknown_error_code(self):
        """Test unknown error code handling"""
        error_code = "UnknownError"
        error_message = "Something unexpected happened"
        
        exception, user_msg = parse_hunyuan_error(error_code, error_message)
        assert isinstance(exception, LLMProviderError)
        assert exception.provider == 'hunyuan'
        assert exception.error_code == error_code


class TestErrorParserIntegration:
    """Test error parser integration with actual API response formats"""
    
    def test_dashscope_parse_and_raise(self):
        """Test parse_and_raise_dashscope_error raises correct exception"""
        error_text = json.dumps({
            "error": {
                "code": "InvalidApiKey",
                "message": "Invalid API-key provided."
            }
        })
        
        with pytest.raises(LLMAccessDeniedError) as exc_info:
            parse_and_raise_dashscope_error(401, error_text)
        
        assert exc_info.value.provider == 'dashscope'
        assert exc_info.value.error_code == 'InvalidApiKey'
        assert hasattr(exc_info.value, 'user_message')
        assert exc_info.value.user_message is not None
    
    def test_hunyuan_parse_and_raise(self):
        """Test parse_and_raise_hunyuan_error raises correct exception"""
        error_code = "AuthFailure.InvalidSecretId"
        error_message = "密钥非法"
        
        with pytest.raises(LLMAccessDeniedError) as exc_info:
            parse_and_raise_hunyuan_error(error_code, error_message)
        
        assert exc_info.value.provider == 'hunyuan'
        assert exc_info.value.error_code == error_code
        assert hasattr(exc_info.value, 'user_message')
        assert exc_info.value.user_message is not None
    
    def test_error_message_preservation(self):
        """Test that original error messages are preserved"""
        error_text = json.dumps({
            "error": {
                "code": "InvalidParameter",
                "message": "Range of input length should be [1, 200000]"
            }
        })
        
        exception, user_msg = parse_dashscope_error(400, error_text)
        assert "Range of input length" in str(exception)
        assert user_msg is not None
        assert len(user_msg) > 0


class TestRealWorldErrorScenarios:
    """Test real-world error scenarios from server logs"""
    
    def test_http_401_unauthorized_from_log(self):
        """Test HTTP 401 error as it appears in logs"""
        # Simulating error from log: "HTTP 401: Unauthorized"
        error_text = '{"error": {"code": "InvalidApiKey", "message": "Invalid API-key provided."}}'
        
        exception, user_msg = parse_dashscope_error(401, error_text)
        assert isinstance(exception, LLMAccessDeniedError)
        assert 'API密钥' in user_msg or 'api key' in user_msg.lower()
    
    def test_rate_limit_from_log(self):
        """Test rate limit error as it appears in logs"""
        error_text = json.dumps({
            "error": {
                "code": "Throttling.RateQuota",
                "message": "Requests rate limit exceeded, please try again later."
            }
        })
        
        exception, user_msg = parse_dashscope_error(429, error_text)
        assert isinstance(exception, LLMRateLimitError)
        assert '请求过于频繁' in user_msg or 'rate limit' in user_msg.lower()
    
    def test_timeout_from_log(self):
        """Test timeout error as it appears in logs"""
        error_text = json.dumps({
            "error": {
                "code": "RequestTimeOut",
                "message": "Request timed out, please try again later."
            }
        })
        
        exception, user_msg = parse_dashscope_error(500, error_text)
        assert isinstance(exception, LLMTimeoutError)
        assert '请求超时' in user_msg or 'timeout' in user_msg.lower()
    
    def test_content_filter_from_log(self):
        """Test content filter error as it appears in logs"""
        error_text = json.dumps({
            "error": {
                "code": "DataInspectionFailed",
                "message": "Input data may contain inappropriate content."
            }
        })
        
        exception, user_msg = parse_dashscope_error(400, error_text)
        assert isinstance(exception, LLMContentFilterError)
        assert '不当信息' in user_msg or 'inappropriate' in user_msg.lower()
    
    def test_quota_exhausted_from_log(self):
        """Test quota exhausted error as it appears in logs"""
        error_code = "FailedOperation.ResourcePackExhausted"
        error_message = "资源包余量已用尽，请购买资源包或开通后付费"
        
        exception, user_msg = parse_hunyuan_error(error_code, error_message)
        assert isinstance(exception, LLMQuotaExhaustedError)
        assert '资源包余量已用尽' in user_msg or 'resource pack' in user_msg.lower()
    
    def test_model_not_found_from_log(self):
        """Test model not found error as it appears in logs"""
        error_text = json.dumps({
            "error": {
                "code": "ModelNotFound",
                "message": "The model qwen-invalid does not exist."
            }
        })
        
        exception, user_msg = parse_dashscope_error(404, error_text)
        assert isinstance(exception, LLMModelNotFoundError)
        assert '模型不存在' in user_msg or 'not found' in user_msg.lower()


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])

