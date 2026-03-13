import json
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from checkin import classify_user_info_error, get_user_info


class MockResponse:
	def __init__(self, status_code, text='', headers=None, json_data=None):
		self.status_code = status_code
		self._text = text
		self._json_data = json_data
		self.headers = headers if headers else {}
		if json_data is not None and not text:
			self._text = json.dumps(json_data)

	@property
	def text(self):
		return self._text

	def json(self):
		if self._json_data is not None:
			return self._json_data
		return json.loads(self._text)


class TestUserInfoErrorClassification:
	def test_classify_json_decode_error(self):
		try:
			json.loads('invalid json')
		except json.JSONDecodeError as e:
			exc = e
		code, msg = classify_user_info_error(None, exc)
		assert code == 'INVALID_JSON'

	def test_classify_401_unauthorized(self):
		response = MockResponse(401, text='Unauthorized')
		code, msg = classify_user_info_error(response)
		assert code == 'COOKIES_INVALID'

	def test_classify_403_forbidden(self):
		response = MockResponse(403, text='Forbidden')
		code, msg = classify_user_info_error(response)
		assert code == 'COOKIES_INVALID'

	def test_classify_500_server_error(self):
		response = MockResponse(500, text='Internal Error')
		code, msg = classify_user_info_error(response)
		assert code == 'HTTP_SERVER_ERROR'

	def test_classify_empty_response(self):
		response = MockResponse(200, text='', headers={'Content-Type': 'application/json'})
		code, msg = classify_user_info_error(response)
		assert code == 'EMPTY_RESPONSE'

	def test_classify_login_page_html(self):
		html = '<!DOCTYPE html><html><form action="/login"><input name="password"></form></html>'
		response = MockResponse(200, text=html, headers={'Content-Type': 'text/html'})
		code, msg = classify_user_info_error(response)
		assert code == 'LOGIN_PAGE'

	def test_classify_challenge_page(self):
		html = '<html><body>Please complete the verification challenge</body></html>'
		response = MockResponse(200, text=html, headers={'Content-Type': 'text/html'})
		code, msg = classify_user_info_error(response)
		assert code == 'CHALLENGE_PAGE'

	def test_classify_invalid_content_type(self):
		response = MockResponse(200, text='some text', headers={'Content-Type': 'text/plain'})
		code, msg = classify_user_info_error(response)
		assert code == 'INVALID_CONTENT_TYPE'


class TestGetUserInfo:
	def test_get_user_info_success(self):
		json_data = {
			'success': True,
			'data': {
				'quota': 1000000,
				'used_quota': 500000
			}
		}
		mock_response = MockResponse(
			200,
			headers={'Content-Type': 'application/json'},
			json_data=json_data
		)

		mock_client = MagicMock()
		mock_client.get.return_value = mock_response

		result = get_user_info(mock_client, {}, 'http://test.com/api/user/self')

		assert result['success'] == True
		assert result['quota'] == 2.0
		assert result['used_quota'] == 1.0

	def test_get_user_info_returns_html(self):
		html = '<!DOCTYPE html><html><body>Login Page</body></html>'
		mock_response = MockResponse(
			200,
			text=html,
			headers={'Content-Type': 'text/html'}
		)

		mock_client = MagicMock()
		mock_client.get.return_value = mock_response

		result = get_user_info(mock_client, {}, 'http://test.com/api/user/self')

		assert result['success'] == False
		assert 'error_code' in result

	def test_get_user_info_empty_response(self):
		mock_response = MockResponse(
			200,
			text='',
			headers={'Content-Type': 'application/json'}
		)

		mock_client = MagicMock()
		mock_client.get.return_value = mock_response

		result = get_user_info(mock_client, {}, 'http://test.com/api/user/self')

		assert result['success'] == False
		assert result['error_code'] == 'EMPTY_RESPONSE'

	def test_get_user_info_403_forbidden(self):
		mock_response = MockResponse(403, text='Forbidden')

		mock_client = MagicMock()
		mock_client.get.return_value = mock_response

		result = get_user_info(mock_client, {}, 'http://test.com/api/user/self')

		assert result['success'] == False
		assert result['error_code'] == 'COOKIES_INVALID'

	def test_get_user_info_500_error(self):
		mock_response = MockResponse(500, text='Internal Server Error')

		mock_client = MagicMock()
		mock_client.get.return_value = mock_response

		result = get_user_info(mock_client, {}, 'http://test.com/api/user/self')

		assert result['success'] == False
		assert result['error_code'] == 'HTTP_SERVER_ERROR'

	def test_get_user_info_json_parse_failed(self):
		mock_response = MockResponse(
			200,
			text='not valid json',
			headers={'Content-Type': 'application/json'}
		)

		mock_client = MagicMock()
		mock_client.get.return_value = mock_response

		result = get_user_info(mock_client, {}, 'http://test.com/api/user/self')

		assert result['success'] == False
		assert 'JSON parse failed' in result['error']

	def test_get_user_info_invalid_json_structure(self):
		json_data = {
			'success': True,
			'data': {
				'wrong_field': 123
			}
		}
		mock_response = MockResponse(
			200,
			headers={'Content-Type': 'application/json'},
			json_data=json_data
		)

		mock_client = MagicMock()
		mock_client.get.return_value = mock_response

		result = get_user_info(mock_client, {}, 'http://test.com/api/user/self')

		assert result['success'] == False
		assert result['error_code'] == 'INVALID_JSON_STRUCTURE'

	def test_get_user_info_api_error(self):
		json_data = {
			'success': False,
			'msg': 'Invalid token'
		}
		mock_response = MockResponse(
			200,
			headers={'Content-Type': 'application/json'},
			json_data=json_data
		)

		mock_client = MagicMock()
		mock_client.get.return_value = mock_response

		result = get_user_info(mock_client, {}, 'http://test.com/api/user/self')

		assert result['success'] == False
		assert 'Invalid token' in result['error']


class TestAutoCheckInLogic:
	@pytest.mark.asyncio
	async def test_auto_checkin_does_not_print_success_on_failure(self):
		import asyncio
		from unittest.mock import patch
		from io import StringIO
		import sys

		captured_output = StringIO()
		sys.stdout = captured_output

		with patch('checkin.get_user_info') as mock_get_user_info, \
			 patch('checkin.prepare_cookies') as mock_prepare_cookies, \
			 patch('httpx.Client') as mock_client:

			mock_get_user_info.return_value = {
				'success': False,
				'error': 'JSON parse failed',
				'error_code': 'INVALID_JSON'
			}
			mock_prepare_cookies.return_value = {'cookie': 'value'}
			mock_client_instance = MagicMock()
			mock_client.return_value = mock_client_instance

			from utils.config import AccountConfig, ProviderConfig, AppConfig

			provider = ProviderConfig(
				name='agentrouter',
				domain='https://test.com',
				sign_in_path=None,
				user_info_path='/api/user/self'
			)
			app_config = AppConfig(providers={'agentrouter': provider})
			account = AccountConfig(cookies='test=123', api_user='test')

			from checkin import check_in_account
			success, before, after = await check_in_account(account, 0, app_config)

			sys.stdout = sys.__stdout__
			output = captured_output.getvalue()

			assert success == False
			assert 'Check-in completed automatically' not in output
			assert 'Automatic check-in failed' in output or 'FAILED' in output
