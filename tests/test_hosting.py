import unittest
from unittest.mock import patch
from aiohttp import web
from aiohttp.test_utils import make_mocked_request
from app.portal import set_cookie
from app import main

class HostingTests(unittest.TestCase):
    def test_render_port_is_used(self):
        with patch.dict('os.environ',{'PORT':'10000'}), patch('sys.argv',['harvestshield','--host','0.0.0.0']), patch.object(main,'create_app',return_value='app'), patch.object(main.web,'run_app') as run:
            main.main()
        run.assert_called_once_with('app',host='0.0.0.0',port=10000)

    def test_explicit_hosted_mode_enforces_secure_cookies(self):
        response=web.Response()
        with patch.dict('os.environ',{'HARVESTSHIELD_SECURE_COOKIES':'1'}):
            set_cookie(response,'random-test-token',make_mocked_request('GET','/'))
        cookie=response.cookies['harvestshield_session']
        self.assertTrue(cookie['secure'])
        self.assertTrue(cookie['httponly'])
        self.assertEqual(cookie['samesite'],'Strict')
