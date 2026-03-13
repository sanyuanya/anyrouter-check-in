"""
测试 get_user_info 和 check_in_account 的逻辑
"""
import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from checkin import get_user_info
from utils.config import AccountConfig, AppConfig, ProviderConfig


class TestGetUserInfo:
	"""测试 get_user_info 函数的各种场景"""

	def test_success_valid_json(self):
		"""user info 返回合法 JSON 且成功"""
		mock_client = MagicMock(spec=httpx.Client)
		mock_response = MagicMock()
		mock_response.status_code = 200
		mock_response.headers = {'content-type': 'application/json'}
		mock_response.text = json.dumps({
			'success': True,
			'data': {
				'quota': 5000000,
				'used_quota': 1000000
			}
		})
		mock_response.json.return_value = {
			'success': True,
			'data': {
				'quota': 5000000,
				'used_quota': 1000000
			}
		}
		mock_client.get.return_value = mock_response

		result = get_user_info(mock_client, {}, 'https://example.com/api/user/self', 'TestAccount')

		assert result['success'] is True
		assert result['quota'] == 10.0
		assert result['used_quota'] == 2.0
		assert 'Current balance' in result['display']

	def test_returns_html_login_page(self):
		"""user info 返回 HTML 登录页"""
		mock_client = MagicMock(spec=httpx.Client)
		mock_response = MagicMock()
		mock_response.status_code = 200
		mock_response.headers = {'content-type': 'text/html'}
		mock_response.text = '<html><body><h1>Please Login</h1></body></html>'
		mock_client.get.return_value = mock_response

		result = get_user_info(mock_client, {}, 'https://example.com/api/user/self', 'TestAccount')

		assert result['success'] is False
		assert result['error_type'] == 'html_response'
		assert 'login page' in result['error'].lower()

	def test_returns_html_challenge_page(self):
		"""user info 返回 challenge/验证页"""
		mock_client = MagicMock(spec=httpx.Client)
		mock_response = MagicMock()
		mock_response.status_code = 200
		mock_response.headers = {'content-type': 'text/html'}
		mock_response.text = '<html><body><h1>Verify you are human</h1></body></html>'
		mock_client.get.return_value = mock_response

		result = get_user_info(mock_client, {}, 'https://example.com/api/user/self', 'TestAccount')

		assert result['success'] is False
		assert result['error_type'] == 'html_response'
		assert 'verification' in result['error'].lower() or 'challenge' in result['error'].lower()

	def test_returns_empty_string(self):
		"""user info 返回空字符串"""
		mock_client = MagicMock(spec=httpx.Client)
		mock_response = MagicMock()
		mock_response.status_code = 200
		mock_response.headers = {'content-type': 'application/json'}
		mock_response.text = ''
		mock_client.get.return_value = mock_response

		result = get_user_info(mock_client, {}, 'https://example.com/api/user/self', 'TestAccount')

		assert result['success'] is False
		assert result['error_type'] == 'empty_response'

	def test_returns_http_403(self):
		"""user info 返回 403"""
		mock_client = MagicMock(spec=httpx.Client)
		mock_response = MagicMock()
		mock_response.status_code = 403
		mock_response.headers = {'content-type': 'application/json'}
		mock_response.text = '{"error": "forbidden"}'
		mock_client.get.return_value = mock_response

		result = get_user_info(mock_client, {}, 'https://example.com/api/user/self', 'TestAccount')

		assert result['success'] is False
		assert result['error_type'] == 'auth_error'
		assert '403' in result['error'] or 'Authentication' in result['error']

	def test_returns_http_500(self):
		"""user info 返回 500"""
		mock_client = MagicMock(spec=httpx.Client)
		mock_response = MagicMock()
		mock_response.status_code = 500
		mock_response.headers = {'content-type': 'application/json'}
		mock_response.text = '{"error": "internal server error"}'
		mock_client.get.return_value = mock_response

		result = get_user_info(mock_client, {}, 'https://example.com/api/user/self', 'TestAccount')

		assert result['success'] is False
		assert result['error_type'] == 'http_error'
		assert '500' in result['error']

	def test_json_parse_error(self):
		"""user info JSON 解析失败"""
		mock_client = MagicMock(spec=httpx.Client)
		mock_response = MagicMock()
		mock_response.status_code = 200
		mock_response.headers = {'content-type': 'application/json'}
		mock_response.text = 'this is not valid json {{{'
		mock_response.json.side_effect = json.JSONDecodeError('Expecting value', 'doc', 0)
		mock_client.get.return_value = mock_response

		result = get_user_info(mock_client, {}, 'https://example.com/api/user/self', 'TestAccount')

		assert result['success'] is False
		assert result['error_type'] == 'json_parse_error'

	def test_api_returns_success_false(self):
		"""API 返回 success=false"""
		mock_client = MagicMock(spec=httpx.Client)
		mock_response = MagicMock()
		mock_response.status_code = 200
		mock_response.headers = {'content-type': 'application/json'}
		mock_response.text = json.dumps({'success': False, 'message': 'User not found'})
		mock_response.json.return_value = {'success': False, 'message': 'User not found'}
		mock_client.get.return_value = mock_response

		result = get_user_info(mock_client, {}, 'https://example.com/api/user/self', 'TestAccount')

		assert result['success'] is False
		assert result['error_type'] == 'api_error'

	def test_missing_data_field(self):
		"""JSON 结构不符合预期 - 缺少 data 字段"""
		mock_client = MagicMock(spec=httpx.Client)
		mock_response = MagicMock()
		mock_response.status_code = 200
		mock_response.headers = {'content-type': 'application/json'}
		mock_response.text = json.dumps({'success': True})
		mock_response.json.return_value = {'success': True}
		mock_client.get.return_value = mock_response

		result = get_user_info(mock_client, {}, 'https://example.com/api/user/self', 'TestAccount')

		assert result['success'] is False
		assert result['error_type'] == 'invalid_structure'

	def test_timeout_error(self):
		"""请求超时"""
		mock_client = MagicMock(spec=httpx.Client)
		mock_client.get.side_effect = httpx.TimeoutException('timeout')

		result = get_user_info(mock_client, {}, 'https://example.com/api/user/self', 'TestAccount')

		assert result['success'] is False
		assert result['error_type'] == 'network_error'
		assert 'timeout' in result['error'].lower()

	def test_network_error(self):
		"""网络错误"""
		mock_client = MagicMock(spec=httpx.Client)
		mock_client.get.side_effect = httpx.NetworkError('connection failed')

		result = get_user_info(mock_client, {}, 'https://example.com/api/user/self', 'TestAccount')

		assert result['success'] is False
		assert result['error_type'] == 'network_error'


class TestCheckInAccountAutoMode:
	"""测试 check_in_account 在自动签到模式（如 agentrouter）下的行为"""

	@pytest.fixture
	def auto_checkin_provider_config(self):
		return ProviderConfig(
			name='test_auto',
			domain='https://test.example.com',
			sign_in_path=None,  # 无需手动签到
			user_info_path='/api/user/self',
			api_user_key='new-api-user',
			bypass_method=None,
		)

	@pytest.fixture
	def app_config_with_auto_provider(self, auto_checkin_provider_config):
		return AppConfig(providers={'test_auto': auto_checkin_provider_config})

	@pytest.fixture
	def account_config(self):
		return AccountConfig(
			cookies={'session': 'test_session'},
			api_user='12345',
			provider='test_auto',
			name='Test Auto Account'
		)

	def _create_mock_client(self, status_code, content_type, text, json_data=None):
		"""创建 mock httpx.Client"""
		mock_client = MagicMock()
		mock_response = MagicMock()
		mock_response.status_code = status_code
		mock_response.headers = {'content-type': content_type}
		mock_response.text = text
		if json_data is not None:
			mock_response.json.return_value = json_data
		mock_client.get.return_value = mock_response
		mock_client.cookies = MagicMock()
		return mock_client

	@patch('checkin.prepare_cookies')
	@patch('httpx.Client')
	def test_auto_checkin_success_when_user_info_succeeds(
		self, mock_client_class, mock_prepare_cookies,
		account_config, app_config_with_auto_provider
	):
		"""自动签到模式：user info 成功时，签到判定为成功"""
		mock_prepare_cookies.return_value = {'session': 'test'}

		json_data = {
			'success': True,
			'data': {'quota': 5000000, 'used_quota': 1000000}
		}
		mock_client = self._create_mock_client(
			200, 'application/json',
			json.dumps(json_data),
			json_data
		)
		mock_client_class.return_value = mock_client

		import asyncio
		from checkin import check_in_account

		success, before, after = asyncio.run(check_in_account(account_config, 0, app_config_with_auto_provider))

		assert success is True
		assert before is not None
		assert before.get('success') is True

	@patch('checkin.prepare_cookies')
	@patch('httpx.Client')
	def test_auto_checkin_fails_when_user_info_returns_html(
		self, mock_client_class, mock_prepare_cookies,
		account_config, app_config_with_auto_provider
	):
		"""自动签到模式：user info 返回 HTML 时，签到判定为失败，不能打印成功日志"""
		mock_prepare_cookies.return_value = {'session': 'test'}

		mock_client = self._create_mock_client(
			200, 'text/html',
			'<html><body>Please Login</body></html>'
		)
		mock_client_class.return_value = mock_client

		import asyncio
		from checkin import check_in_account

		success, before, after = asyncio.run(check_in_account(account_config, 0, app_config_with_auto_provider))

		assert success is False, "当 user info 返回 HTML 时，签到应该失败"
		assert before is not None
		assert before.get('success') is False
		assert before.get('error_type') == 'html_response'

	@patch('checkin.prepare_cookies')
	@patch('httpx.Client')
	def test_auto_checkin_fails_when_user_info_returns_empty(
		self, mock_client_class, mock_prepare_cookies,
		account_config, app_config_with_auto_provider
	):
		"""自动签到模式：user info 返回空响应时，签到判定为失败"""
		mock_prepare_cookies.return_value = {'session': 'test'}

		mock_client = self._create_mock_client(200, 'application/json', '')
		mock_client_class.return_value = mock_client

		import asyncio
		from checkin import check_in_account

		success, before, after = asyncio.run(check_in_account(account_config, 0, app_config_with_auto_provider))

		assert success is False, "当 user info 返回空响应时，签到应该失败"
		assert before is not None
		assert before.get('success') is False
		assert before.get('error_type') == 'empty_response'

	@patch('checkin.prepare_cookies')
	@patch('httpx.Client')
	def test_auto_checkin_fails_when_user_info_returns_403(
		self, mock_client_class, mock_prepare_cookies,
		account_config, app_config_with_auto_provider
	):
		"""自动签到模式：user info 返回 403 时，签到判定为失败"""
		mock_prepare_cookies.return_value = {'session': 'test'}

		mock_client = self._create_mock_client(
			403, 'application/json',
			'{"error": "forbidden"}'
		)
		mock_client_class.return_value = mock_client

		import asyncio
		from checkin import check_in_account

		success, before, after = asyncio.run(check_in_account(account_config, 0, app_config_with_auto_provider))

		assert success is False, "当 user info 返回 403 时，签到应该失败"
		assert before is not None
		assert before.get('success') is False
		assert before.get('error_type') == 'auth_error'

	@patch('checkin.prepare_cookies')
	@patch('httpx.Client')
	def test_auto_checkin_fails_when_json_parse_error(
		self, mock_client_class, mock_prepare_cookies,
		account_config, app_config_with_auto_provider
	):
		"""自动签到模式：JSON 解析失败时，签到判定为失败"""
		mock_prepare_cookies.return_value = {'session': 'test'}

		mock_client = MagicMock()
		mock_response = MagicMock()
		mock_response.status_code = 200
		mock_response.headers = {'content-type': 'application/json'}
		mock_response.text = 'invalid json'
		mock_response.json.side_effect = json.JSONDecodeError('Expecting value', 'doc', 0)
		mock_client.get.return_value = mock_response
		mock_client.cookies = MagicMock()
		mock_client_class.return_value = mock_client

		import asyncio
		from checkin import check_in_account

		success, before, after = asyncio.run(check_in_account(account_config, 0, app_config_with_auto_provider))

		assert success is False, "当 JSON 解析失败时，签到应该失败"
		assert before is not None
		assert before.get('success') is False
		assert before.get('error_type') == 'json_parse_error'

	@patch('checkin.prepare_cookies')
	@patch('httpx.Client')
	def test_auto_checkin_never_prints_success_on_failure(
		self, mock_client_class, mock_prepare_cookies,
		account_config, app_config_with_auto_provider, capsys
	):
		"""失败场景下绝不能打印 'Check-in completed automatically'"""
		mock_prepare_cookies.return_value = {'session': 'test'}

		mock_client = self._create_mock_client(
			200, 'text/html',
			'<html><body>Please Login</body></html>'
		)
		mock_client_class.return_value = mock_client

		import asyncio
		from checkin import check_in_account

		success, before, after = asyncio.run(check_in_account(account_config, 0, app_config_with_auto_provider))

		captured = capsys.readouterr()

		assert success is False
		assert 'Check-in completed automatically' not in captured.out, \
			"失败场景下不应打印 'Check-in completed automatically'"
		assert '[FAILED]' in captured.out, "失败场景下应打印 '[FAILED]' 日志"


class TestCheckInAccountManualMode:
	"""测试 check_in_account 在手动签到模式（如 anyrouter）下的行为"""

	@pytest.fixture
	def manual_checkin_provider_config(self):
		return ProviderConfig(
			name='test_manual',
			domain='https://test.example.com',
			sign_in_path='/api/user/sign_in',  # 需要手动签到
			user_info_path='/api/user/self',
			api_user_key='new-api-user',
			bypass_method=None,
		)

	@pytest.fixture
	def app_config_with_manual_provider(self, manual_checkin_provider_config):
		return AppConfig(providers={'test_manual': manual_checkin_provider_config})

	@pytest.fixture
	def account_config(self):
		return AccountConfig(
			cookies={'session': 'test_session'},
			api_user='12345',
			provider='test_manual',
			name='Test Manual Account'
		)

	@patch('checkin.execute_check_in')
	@patch('checkin.prepare_cookies')
	@patch('httpx.Client')
	def test_manual_checkin_uses_separate_checkin_endpoint(
		self, mock_client_class, mock_prepare_cookies, mock_execute_check_in,
		account_config, app_config_with_manual_provider
	):
		"""手动签到模式：应该调用独立的签到接口"""
		mock_prepare_cookies.return_value = {'session': 'test'}
		mock_execute_check_in.return_value = True

		mock_client = MagicMock()
		mock_response = MagicMock()
		mock_response.status_code = 200
		mock_response.headers = {'content-type': 'application/json'}
		mock_response.text = json.dumps({
			'success': True,
			'data': {'quota': 5000000, 'used_quota': 1000000}
		})
		mock_response.json.return_value = {
			'success': True,
			'data': {'quota': 5000000, 'used_quota': 1000000}
		}
		mock_client.get.return_value = mock_response
		mock_client_class.return_value.__enter__ = MagicMock(return_value=mock_client)
		mock_client_class.return_value.__exit__ = MagicMock(return_value=False)
		mock_client.cookies = MagicMock()

		import asyncio
		from checkin import check_in_account

		success, before, after = asyncio.run(check_in_account(account_config, 0, app_config_with_manual_provider))

		mock_execute_check_in.assert_called_once()
		assert success is True
