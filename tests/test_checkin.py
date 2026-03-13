#!/usr/bin/env python3
"""
Check-in 模块的回归测试
"""

import json
import pytest
from unittest.mock import Mock, patch

import sys
sys.path.insert(0, '/Users/sanyuanyanikezhenchou/hjworkspace/anyrouter-check-in')

from checkin import (
    get_user_info,
    UserInfoError,
    CookieExpiredError,
    ChallengePageError,
    LoginPageError,
    EmptyResponseError,
    NonJsonResponseError,
    HttpError,
    InvalidJsonStructureError,
)


class MockResponse:
    """模拟 HTTP 响应"""

    def __init__(self, status_code=200, text='', headers=None, json_data=None):
        self.status_code = status_code
        self._text = text
        self.headers = headers or {}
        self._json_data = json_data

    @property
    def text(self):
        if self._text:
            return self._text
        if self._json_data is not None:
            return json.dumps(self._json_data)
        return ''

    def json(self):
        if self._json_data is not None:
            return self._json_data
        return json.loads(self._text)


class TestGetUserInfo:
    """测试 get_user_info 函数"""

    def test_success_valid_json(self):
        """测试：user info 返回合法 JSON 且成功"""
        mock_client = Mock()
        mock_response = MockResponse(
            status_code=200,
            headers={'Content-Type': 'application/json'},
            json_data={
                'success': True,
                'data': {
                    'quota': 1000000,  # 2.00 after division
                    'used_quota': 500000,  # 1.00 after division
                }
            }
        )
        mock_client.get.return_value = mock_response

        result = get_user_info(mock_client, {}, 'https://example.com/api/user/self', 'TestAccount')

        assert result['success'] is True
        assert result['quota'] == 2.00
        assert result['used_quota'] == 1.00
        assert ':money:' in result['display']

    def test_returns_html_login_page(self):
        """测试：user info 返回 HTML 登录页"""
        mock_client = Mock()
        mock_response = MockResponse(
            status_code=200,
            text='<html><body><form action="/login">Login</form></body></html>',
            headers={'Content-Type': 'text/html'}
        )
        mock_client.get.return_value = mock_response

        with pytest.raises(LoginPageError) as exc_info:
            get_user_info(mock_client, {}, 'https://example.com/api/user/self', 'TestAccount')

        assert exc_info.value.error_type == 'login_page'
        assert 'login' in exc_info.value.message.lower()

    def test_returns_html_challenge_page(self):
        """测试：user info 返回 challenge/verification 页面"""
        mock_client = Mock()
        mock_response = MockResponse(
            status_code=200,
            text='<html><body>WAF Challenge Verification</body></html>',
            headers={'Content-Type': 'text/html'}
        )
        mock_client.get.return_value = mock_response

        with pytest.raises(ChallengePageError) as exc_info:
            get_user_info(mock_client, {}, 'https://example.com/api/user/self', 'TestAccount')

        assert exc_info.value.error_type == 'challenge_page'

    def test_returns_empty_string(self):
        """测试：user info 返回空字符串"""
        mock_client = Mock()
        mock_response = MockResponse(
            status_code=200,
            text='',
            headers={'Content-Type': 'application/json'}
        )
        mock_client.get.return_value = mock_response

        with pytest.raises(EmptyResponseError) as exc_info:
            get_user_info(mock_client, {}, 'https://example.com/api/user/self', 'TestAccount')

        assert exc_info.value.error_type == 'empty_response'

    def test_returns_whitespace_only(self):
        """测试：user info 返回仅包含空白字符的响应"""
        mock_client = Mock()
        mock_response = MockResponse(
            status_code=200,
            text='   \n\t   ',
            headers={'Content-Type': 'application/json'}
        )
        mock_client.get.return_value = mock_response

        with pytest.raises(EmptyResponseError) as exc_info:
            get_user_info(mock_client, {}, 'https://example.com/api/user/self', 'TestAccount')

        assert exc_info.value.error_type == 'empty_response'

    def test_returns_403_forbidden(self):
        """测试：user info 返回 403"""
        mock_client = Mock()
        mock_response = MockResponse(
            status_code=403,
            text='Forbidden',
            headers={'Content-Type': 'text/plain'}
        )
        mock_client.get.return_value = mock_response

        with pytest.raises(CookieExpiredError) as exc_info:
            get_user_info(mock_client, {}, 'https://example.com/api/user/self', 'TestAccount')

        assert exc_info.value.error_type == 'cookie_expired'
        assert exc_info.value.status_code == 403

    def test_returns_401_unauthorized(self):
        """测试：user info 返回 401"""
        mock_client = Mock()
        mock_response = MockResponse(
            status_code=401,
            text='Unauthorized',
            headers={'Content-Type': 'text/plain'}
        )
        mock_client.get.return_value = mock_response

        with pytest.raises(CookieExpiredError) as exc_info:
            get_user_info(mock_client, {}, 'https://example.com/api/user/self', 'TestAccount')

        assert exc_info.value.error_type == 'cookie_expired'
        assert exc_info.value.status_code == 401

    def test_returns_500_server_error(self):
        """测试：user info 返回 500"""
        mock_client = Mock()
        mock_response = MockResponse(
            status_code=500,
            text='Internal Server Error',
            headers={'Content-Type': 'text/plain'}
        )
        mock_client.get.return_value = mock_response

        with pytest.raises(HttpError) as exc_info:
            get_user_info(mock_client, {}, 'https://example.com/api/user/self', 'TestAccount')

        assert exc_info.value.error_type == 'http_server_error'
        assert exc_info.value.status_code == 500

    def test_returns_400_bad_request(self):
        """测试：user info 返回 400"""
        mock_client = Mock()
        mock_response = MockResponse(
            status_code=400,
            text='Bad Request',
            headers={'Content-Type': 'text/plain'}
        )
        mock_client.get.return_value = mock_response

        with pytest.raises(HttpError) as exc_info:
            get_user_info(mock_client, {}, 'https://example.com/api/user/self', 'TestAccount')

        assert exc_info.value.error_type == 'http_client_error'
        assert exc_info.value.status_code == 400

    def test_json_parse_failure(self):
        """测试：user info JSON 解析失败"""
        mock_client = Mock()
        mock_response = MockResponse(
            status_code=200,
            text='not valid json {',
            headers={'Content-Type': 'application/json'}
        )
        mock_client.get.return_value = mock_response

        with pytest.raises(NonJsonResponseError) as exc_info:
            get_user_info(mock_client, {}, 'https://example.com/api/user/self', 'TestAccount')

        assert exc_info.value.error_type == 'json_decode_error'

    def test_json_structure_missing_success_field(self):
        """测试：JSON 结构不符合预期 - 缺少 success 字段"""
        mock_client = Mock()
        mock_response = MockResponse(
            status_code=200,
            headers={'Content-Type': 'application/json'},
            json_data={'data': {'quota': 1000000}}  # 缺少 success 字段
        )
        mock_client.get.return_value = mock_response

        with pytest.raises(InvalidJsonStructureError) as exc_info:
            get_user_info(mock_client, {}, 'https://example.com/api/user/self', 'TestAccount')

        assert exc_info.value.error_type == 'api_error'

    def test_json_structure_success_false(self):
        """测试：JSON 结构不符合预期 - success 为 false"""
        mock_client = Mock()
        mock_response = MockResponse(
            status_code=200,
            headers={'Content-Type': 'application/json'},
            json_data={'success': False, 'message': 'Invalid token'}
        )
        mock_client.get.return_value = mock_response

        with pytest.raises(InvalidJsonStructureError) as exc_info:
            get_user_info(mock_client, {}, 'https://example.com/api/user/self', 'TestAccount')

        assert exc_info.value.error_type == 'api_error'
        assert 'Invalid token' in exc_info.value.message

    def test_json_structure_not_dict(self):
        """测试：JSON 结构不符合预期 - 返回数组而非对象"""
        mock_client = Mock()
        mock_response = MockResponse(
            status_code=200,
            headers={'Content-Type': 'application/json'},
            json_data=['item1', 'item2']  # 数组而非字典
        )
        mock_client.get.return_value = mock_response

        with pytest.raises(InvalidJsonStructureError) as exc_info:
            get_user_info(mock_client, {}, 'https://example.com/api/user/self', 'TestAccount')

        assert exc_info.value.error_type == 'invalid_json_structure'

    def test_invalid_user_data_format(self):
        """测试：user data 不是字典"""
        mock_client = Mock()
        mock_response = MockResponse(
            status_code=200,
            headers={'Content-Type': 'application/json'},
            json_data={'success': True, 'data': 'invalid'}  # data 不是字典
        )
        mock_client.get.return_value = mock_response

        with pytest.raises(InvalidJsonStructureError) as exc_info:
            get_user_info(mock_client, {}, 'https://example.com/api/user/self', 'TestAccount')

        assert exc_info.value.error_type == 'invalid_user_data'

    def test_response_preview_truncated(self):
        """测试：响应预览被正确截断到 200 字符"""
        mock_client = Mock()
        long_html = '<html><form action="/login">' + 'a' * 1000 + '</form></html>'
        mock_response = MockResponse(
            status_code=200,
            text=long_html,
            headers={'Content-Type': 'text/html'}
        )
        mock_client.get.return_value = mock_response

        with pytest.raises(LoginPageError) as exc_info:
            get_user_info(mock_client, {}, 'https://example.com/api/user/self', 'TestAccount')

        assert len(exc_info.value.response_preview) <= 200


class TestCheckInAccountLogic:
    """测试签到账号的业务逻辑"""

    @pytest.mark.asyncio
    @patch('checkin.get_user_info')
    @patch('checkin.prepare_cookies')
    @patch('checkin.parse_cookies')
    async def test_auto_checkin_success_when_user_info_succeeds(self, mock_parse, mock_prepare, mock_get_info):
        """测试：自动签到场景下，user info 成功时才算签到成功"""
        from checkin import check_in_account, AccountConfig
        from utils.config import AppConfig, ProviderConfig

        # 设置 provider 配置（自动签到类型）
        mock_provider = Mock(spec=ProviderConfig)
        mock_provider.domain = 'https://agentrouter.org'
        mock_provider.user_info_path = '/api/user/self'
        mock_provider.api_user_key = 'new-api-user'
        mock_provider.needs_manual_check_in.return_value = False  # 自动签到
        mock_provider.needs_waf_cookies.return_value = False

        mock_app_config = Mock(spec=AppConfig)
        mock_app_config.get_provider.return_value = mock_provider

        # 设置 cookies
        mock_parse.return_value = {'session': 'test'}
        mock_prepare.return_value = {'session': 'test'}

        # 模拟 user info 成功返回（两次调用都成功）
        mock_get_info.return_value = {
            'success': True,
            'quota': 2.0,
            'used_quota': 1.0,
            'display': ':money: Current balance: $2.0, Used: $1.0'
        }

        account = AccountConfig(cookies='session=test', api_user='test_user', provider='agentrouter', name='Test')

        success, user_info_before, user_info_after = await check_in_account(account, 0, mock_app_config)

        assert success is True
        assert user_info_before is not None
        assert user_info_after is not None

    @pytest.mark.asyncio
    @patch('checkin.get_user_info')
    @patch('checkin.prepare_cookies')
    @patch('checkin.parse_cookies')
    async def test_auto_checkin_failure_when_user_info_fails(self, mock_parse, mock_prepare, mock_get_info):
        """测试：自动签到场景下，user info 失败时绝不能判定为成功"""
        from checkin import check_in_account, AccountConfig
        from utils.config import AppConfig, ProviderConfig

        # 设置 provider 配置（自动签到类型）
        mock_provider = Mock(spec=ProviderConfig)
        mock_provider.domain = 'https://agentrouter.org'
        mock_provider.user_info_path = '/api/user/self'
        mock_provider.api_user_key = 'new-api-user'
        mock_provider.needs_manual_check_in.return_value = False  # 自动签到
        mock_provider.needs_waf_cookies.return_value = False

        mock_app_config = Mock(spec=AppConfig)
        mock_app_config.get_provider.return_value = mock_provider

        # 设置 cookies
        mock_parse.return_value = {'session': 'test'}
        mock_prepare.return_value = {'session': 'test'}

        # 模拟 user info 失败（抛出异常）
        mock_get_info.side_effect = CookieExpiredError(
            'cookie_expired', 'Auth failed', 403, 'text/html', '<html>login</html>'
        )

        account = AccountConfig(cookies='session=test', api_user='test_user', provider='agentrouter', name='Test')

        success, user_info_before, user_info_after = await check_in_account(account, 0, mock_app_config)

        # 关键断言：user info 失败时，签到必须判定为失败
        assert success is False
        assert user_info_before is None
        assert user_info_after is None

    @pytest.mark.asyncio
    @patch('checkin.get_user_info')
    @patch('checkin.prepare_cookies')
    @patch('checkin.parse_cookies')
    async def test_auto_checkin_failure_on_html_response(self, mock_parse, mock_prepare, mock_get_info):
        """测试：自动签到场景下，返回 HTML 时绝不能判定为成功"""
        from checkin import check_in_account, AccountConfig
        from utils.config import AppConfig, ProviderConfig

        mock_provider = Mock(spec=ProviderConfig)
        mock_provider.domain = 'https://agentrouter.org'
        mock_provider.user_info_path = '/api/user/self'
        mock_provider.api_user_key = 'new-api-user'
        mock_provider.needs_manual_check_in.return_value = False
        mock_provider.needs_waf_cookies.return_value = False

        mock_app_config = Mock(spec=AppConfig)
        mock_app_config.get_provider.return_value = mock_provider

        mock_parse.return_value = {'session': 'test'}
        mock_prepare.return_value = {'session': 'test'}

        # 模拟返回 HTML 登录页
        mock_get_info.side_effect = LoginPageError(
            'login_page', 'Redirected to login', 200, 'text/html', '<html><form>login</form></html>'
        )

        account = AccountConfig(cookies='session=test', api_user='test_user', provider='agentrouter', name='Test')

        success, user_info_before, user_info_after = await check_in_account(account, 0, mock_app_config)

        # 关键断言：返回 HTML 登录页时，签到必须判定为失败
        assert success is False

    @pytest.mark.asyncio
    @patch('checkin.get_user_info')
    @patch('checkin.prepare_cookies')
    @patch('checkin.parse_cookies')
    async def test_auto_checkin_failure_on_empty_response(self, mock_parse, mock_prepare, mock_get_info):
        """测试：自动签到场景下，返回空响应时绝不能判定为成功"""
        from checkin import check_in_account, AccountConfig
        from utils.config import AppConfig, ProviderConfig

        mock_provider = Mock(spec=ProviderConfig)
        mock_provider.domain = 'https://agentrouter.org'
        mock_provider.user_info_path = '/api/user/self'
        mock_provider.api_user_key = 'new-api-user'
        mock_provider.needs_manual_check_in.return_value = False
        mock_provider.needs_waf_cookies.return_value = False

        mock_app_config = Mock(spec=AppConfig)
        mock_app_config.get_provider.return_value = mock_provider

        mock_parse.return_value = {'session': 'test'}
        mock_prepare.return_value = {'session': 'test'}

        # 模拟返回空响应
        mock_get_info.side_effect = EmptyResponseError(
            'empty_response', 'Empty body', 200, 'application/json', '<empty>'
        )

        account = AccountConfig(cookies='session=test', api_user='test_user', provider='agentrouter', name='Test')

        success, user_info_before, user_info_after = await check_in_account(account, 0, mock_app_config)

        # 关键断言：返回空响应时，签到必须判定为失败
        assert success is False

    @pytest.mark.asyncio
    @patch('checkin.get_user_info')
    @patch('checkin.prepare_cookies')
    @patch('checkin.parse_cookies')
    async def test_auto_checkin_failure_on_json_decode_error(self, mock_parse, mock_prepare, mock_get_info):
        """测试：自动签到场景下，JSON 解析失败时绝不能判定为成功"""
        from checkin import check_in_account, AccountConfig
        from utils.config import AppConfig, ProviderConfig

        mock_provider = Mock(spec=ProviderConfig)
        mock_provider.domain = 'https://agentrouter.org'
        mock_provider.user_info_path = '/api/user/self'
        mock_provider.api_user_key = 'new-api-user'
        mock_provider.needs_manual_check_in.return_value = False
        mock_provider.needs_waf_cookies.return_value = False

        mock_app_config = Mock(spec=AppConfig)
        mock_app_config.get_provider.return_value = mock_provider

        mock_parse.return_value = {'session': 'test'}
        mock_prepare.return_value = {'session': 'test'}

        # 模拟 JSON 解析失败
        mock_get_info.side_effect = NonJsonResponseError(
            'json_decode_error', 'Parse error', 200, 'application/json', 'invalid{'
        )

        account = AccountConfig(cookies='session=test', api_user='test_user', provider='agentrouter', name='Test')

        success, user_info_before, user_info_after = await check_in_account(account, 0, mock_app_config)

        # 关键断言：JSON 解析失败时，签到必须判定为失败
        assert success is False


class TestErrorTypes:
    """测试错误类型的属性"""

    def test_user_info_error_attributes(self):
        """测试 UserInfoError 包含所有必要的属性"""
        error = UserInfoError(
            error_type='test_error',
            message='Test message',
            status_code=500,
            content_type='text/html',
            response_preview='<html>test</html>'
        )

        assert error.error_type == 'test_error'
        assert error.message == 'Test message'
        assert error.status_code == 500
        assert error.content_type == 'text/html'
        assert error.response_preview == '<html>test</html>'

    def test_error_inheritance(self):
        """测试错误类型继承关系"""
        assert issubclass(CookieExpiredError, UserInfoError)
        assert issubclass(ChallengePageError, UserInfoError)
        assert issubclass(LoginPageError, UserInfoError)
        assert issubclass(EmptyResponseError, UserInfoError)
        assert issubclass(NonJsonResponseError, UserInfoError)
        assert issubclass(HttpError, UserInfoError)
        assert issubclass(InvalidJsonStructureError, UserInfoError)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
