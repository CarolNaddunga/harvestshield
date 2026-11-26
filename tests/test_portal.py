from storage_support import test_database
import re
import tempfile
import time
from pathlib import Path
from aiohttp.test_utils import AioHTTPTestCase
from app.database import connect, seed
from app.main import create_app
from app.portal import digest

PASSWORD='portal-test-password'
def token(html):
    return re.search(r'name="csrf" value="([^"]+)"',html).group(1)

class PortalTests(AioHTTPTestCase):
    async def get_application(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path=test_database(self)
        seed(self.path,PASSWORD)
        return create_app(self.path)

    async def login(self,username):
        self.client.session.cookie_jar.clear()
        response=await self.client.get('/login')
        before=self.client.session.cookie_jar.filter_cookies(self.client.make_url('/'))['harvestshield_session'].value
        response=await self.client.post('/login',data={'csrf':token(await response.text()),'username':username,'password':PASSWORD},allow_redirects=False)
        self.assertEqual(response.status,303,await response.text())
        after=self.client.session.cookie_jar.filter_cookies(self.client.make_url('/'))['harvestshield_session'].value
        self.assertNotEqual(before,after)
        with connect(self.path) as db:
            self.assertIsNone(db.execute('SELECT * FROM sessions WHERE token_hash=?',(digest(before),)).fetchone())
        return after

    async def test_farmer_ownership_and_roles(self):
        await self.login('farmer01')
        for path in ['/portal','/farmers','/farmers/1','/deliveries','/deliveries/1']:
            self.assertEqual((await self.client.get(path)).status,200,path)
        for path in ['/farmers/2','/deliveries/2','/audit','/users','/deliveries/new']:
            self.assertEqual((await self.client.get(path)).status,403,path)
        body=await (await self.client.get('/deliveries')).text()
        self.assertIn('Farmer 01',body); self.assertNotIn('Farmer 02',body)
        self.assertEqual((await self.client.post('/deliveries/1/status',data={'status':'approved'})).status,403)

    async def test_end_to_end_clerk_farmer_admin(self):
        await self.login('clerk01')
        body=await (await self.client.get('/deliveries/new')).text()
        response=await self.client.post('/deliveries/new',data={'csrf':token(body),'farmer_id':'1','crop':'maize','quantity':'150','date':'2026-11-01','unit_price_ugx':'1','status':'approved'},allow_redirects=False)
        self.assertEqual(response.status,303,await response.text())
        location=response.headers['Location']; record=int(location.split('/')[-1])
        with connect(self.path) as db:
            item=db.execute('SELECT * FROM deliveries WHERE id=?',(record,)).fetchone()
            self.assertEqual(item['amount_ugx'],180000); self.assertEqual(item['unit_price_ugx'],1200)
            self.assertEqual(item['status'],'pending'); self.assertEqual(item['recorded_by'],11)
        self.assertEqual((await self.client.post(location+'/status',data={'status':'approved'})).status,403)
        await self.login('farmer01')
        body=await (await self.client.get(location)).text()
        self.assertIn('180,000',body); self.assertIn('pending',body)
        await self.login('farmer02'); self.assertEqual((await self.client.get(location)).status,403)
        await self.login('admin'); body=await (await self.client.get(location)).text()
        decision={'csrf':token(body),'status':'approved','expected_status':'pending'}
        self.assertEqual((await self.client.post(location+'/status',data=decision,allow_redirects=False)).status,303)
        body=await (await self.client.get('/audit')).text()
        for text in ['delivery.created','delivery.status_changed','before','after']: self.assertIn(text,body)
        with connect(self.path) as db:
            self.assertEqual(db.execute('SELECT status FROM deliveries WHERE id=?',(record,)).fetchone()[0],'approved')
        response=await self.client.post(location+'/status',data=decision|{'status':'rejected'})
        self.assertEqual(response.status,409)
        await self.login('farmer01'); self.assertIn('approved',await (await self.client.get(location)).text())

    async def test_validation_and_csrf_no_side_effects(self):
        await self.login('clerk02'); body=await (await self.client.get('/deliveries/new')).text()
        data={'csrf':token(body),'farmer_id':'1','crop':'beans','quantity':'12.5','date':'2026-11-01'}
        for extra,expected in [({'quantity':'-1'},400),({'quantity':'NaN'},400),({'farmer_id':'999'},400),({'date':'bad'},400),({'date':'2999-01-01'},400),({'crop':'unknown'},400),({'csrf':'bad'},403),({'csrf':'é'},403),({'csrf':''},403)]:
            with self.subTest(extra=extra):
                response=await self.client.post('/deliveries/new',data=data|extra)
                self.assertEqual(response.status,expected,await response.text())
        with connect(self.path) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM deliveries').fetchone()[0],18)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM audit_events WHERE action='delivery.created'").fetchone()[0],0)

    async def test_logout_invalidates_session(self):
        old=await self.login('admin'); body=await (await self.client.get('/portal')).text()
        self.assertEqual((await self.client.get('/logout')).status,405)
        self.assertEqual((await self.client.post('/logout',data={'csrf':'wrong'})).status,403)
        self.assertEqual((await self.client.post('/logout',data={'csrf':token(body)},allow_redirects=False)).status,303)
        self.client.session.cookie_jar.update_cookies({'harvestshield_session':old})
        self.assertEqual((await self.client.get('/portal',allow_redirects=False)).status,303)

    async def test_expired_and_anonymous_sessions(self):
        for path in ['/portal','/deliveries/1','/farmers/1','/audit','/users']:
            self.assertEqual((await self.client.get(path,allow_redirects=False)).status,303)
        old=await self.login('farmer01')
        with connect(self.path) as db: db.execute('UPDATE sessions SET expires_at=? WHERE token_hash=?',(int(time.time())-1,digest(old)))
        self.assertEqual((await self.client.get('/portal',allow_redirects=False)).status,303)

    async def test_login_csrf_and_rate_limit(self):
        body=await (await self.client.get('/login')).text(); csrf=token(body)
        self.assertEqual((await self.client.post('/login',data={'username':'admin','password':PASSWORD,'csrf':'bad'})).status,403)
        for _ in range(10):
            response=await self.client.post('/login',data={'username':'admin','password':'wrong','csrf':csrf})
            self.assertEqual(response.status,401)
        self.assertEqual((await self.client.post('/login',data={'username':'admin','password':PASSWORD,'csrf':csrf})).status,429)

    async def test_escaping_search_and_approval_checks(self):
        with connect(self.path) as db: db.execute('UPDATE users SET display_name=? WHERE id=1',('<script>alert(1)</script>',))
        await self.login('farmer01'); body=await (await self.client.get('/farmers/1')).text()
        self.assertNotIn('<script>',body); self.assertIn('&lt;script&gt;',body)
        self.assertIn('No deliveries found',await (await self.client.get('/deliveries?q=Farmer%2002')).text())
        await self.login('admin'); body=await (await self.client.get('/deliveries/1')).text()
        for data,expected in [({'csrf':'bad','status':'approved'},403),({'csrf':token(body),'status':'arbitrary'},400)]:
            self.assertEqual((await self.client.post('/deliveries/1/status',data=data)).status,expected)
        with connect(self.path) as db: self.assertEqual(db.execute('SELECT status FROM deliveries WHERE id=1').fetchone()[0],'pending')
