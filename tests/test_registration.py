from aiohttp.test_utils import AioHTTPTestCase
from app.auth import verify_password
from app.database import connect
import test_portal as portal_tests
from test_portal import token

class RegistrationTests(AioHTTPTestCase):
    get_application=portal_tests.PortalTests.get_application

    async def form(self):
        response=await self.client.get('/register')
        self.assertEqual(response.status,200)
        return {'csrf':token(await response.text()),'username':'new_farmer','display_name':'Sample Member','district':'Mukono','password':'new-test-password','confirm_password':'new-test-password'}

    async def test_registration_creates_farmer_and_signs_in(self):
        data=await self.form()
        response=await self.client.post('/register',data=data|{'role':'admin','user_id':'13'},allow_redirects=False)
        self.assertEqual(response.status,303,await response.text())
        self.assertEqual(response.headers['Location'],'/portal')
        self.assertTrue(response.cookies['harvestshield_session']['httponly'])
        self.assertEqual(response.cookies['harvestshield_session']['samesite'],'Strict')
        with connect(self.path) as db:
            user=db.execute("SELECT * FROM users WHERE username='new_farmer'").fetchone()
            self.assertEqual(user['role'],'farmer')
            self.assertTrue(verify_password('new-test-password',user['password_hash']))
            farmer=db.execute('SELECT * FROM farmers WHERE user_id=?',(user['id'],)).fetchone()
            self.assertEqual(farmer['district'],'Mukono')
            self.assertEqual(db.execute("SELECT COUNT(*) FROM audit_events WHERE action='account.created'").fetchone()[0],1)
        body=await (await self.client.get('/portal')).text()
        self.assertIn('Sample Member',body); self.assertIn('No deliveries found',body)
        self.assertEqual((await self.client.get('/audit')).status,403)
        self.assertEqual((await self.client.get('/farmers/1')).status,403)
        self.assertEqual((await self.client.post('/logout',data={'csrf':token(body)},allow_redirects=False)).status,303)
        body=await (await self.client.get('/login')).text()
        response=await self.client.post('/login',data={'csrf':token(body),'username':'new_farmer','password':'new-test-password'},allow_redirects=False)
        self.assertEqual(response.status,303)

    async def test_registration_validation_and_duplicates(self):
        data=await self.form()
        for extra,status in [({'csrf':'bad'},403),({'username':'ADMIN'},409),({'password':'short','confirm_password':'short'},400),({'confirm_password':'different-password'},400),({'district':''},400),({'display_name':''},400),({'username':'bad name'},400)]:
            with self.subTest(extra=extra):
                response=await self.client.post('/register',data=data|extra)
                self.assertEqual(response.status,status,await response.text())
                self.assertNotIn('value="new-test-password"',await response.text())
        with connect(self.path) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM users').fetchone()[0],13)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM farmers').fetchone()[0],10)

    async def test_registration_rate_limit_and_clean_labels(self):
        data=await self.form()
        for _ in range(10):
            self.assertEqual((await self.client.post('/register',data=data|{'username':'!'})).status,400)
        self.assertEqual((await self.client.post('/register',data=data)).status,429)
        body=await (await self.client.get('/login')).text()
        self.assertIn('Create an account',body)
        self.assertNotIn('LOCAL DEMO',body); self.assertNotIn('Use the local demo password',body)
        self.assertNotIn('Accounts: farmer01',body)
        self.assertNotIn('LOCAL DEMO',await (await self.client.get('/')).text())
