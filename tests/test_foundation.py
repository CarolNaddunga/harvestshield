from storage_support import test_database
import sqlite3
import tempfile
import unittest
from pathlib import Path
from aiohttp.test_utils import AioHTTPTestCase
from app.auth import verify_password
from app.database import connect, overview, seed
from app.main import create_app
from app.models import calculate_amount


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=test_database(self)
        seed(self.path, 'test-only-password')

    def test_seed_is_repeatable_without_overwriting(self):
        self.assertFalse(seed(self.path, 'different-password'))
        with connect(self.path) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM users').fetchone()[0], 13)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM farmers').fetchone()[0], 10)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM deliveries').fetchone()[0], 18)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM audit_events').fetchone()[0], 1)
            rows = db.execute('SELECT password_hash FROM users').fetchall()
            self.assertNotEqual(rows[0][0], rows[1][0])
            self.assertTrue(verify_password('test-only-password', rows[0][0]))
            self.assertFalse(verify_password('wrong-password', rows[0][0]))

    def test_overview_responds_to_database_change(self):
        before, _ = overview(self.path)
        with connect(self.path) as db:
            db.execute("UPDATE deliveries SET status='approved' WHERE id=1")
        after, _ = overview(self.path)
        self.assertEqual(after['pending'], before['pending'] - 1)
        self.assertEqual(after['approved_ugx'], before['approved_ugx'] + 72000)
        self.assertEqual(before['quantity_grams'], 2610000)
        self.assertEqual(before['approved_ugx'], 8829000)

    def test_schema_rejects_inconsistent_amount(self):
        with self.assertRaises(sqlite3.IntegrityError):
            with connect(self.path) as db:
                db.execute('UPDATE deliveries SET amount_ugx=1 WHERE id=1')

    def test_decimal_amount(self):
        self.assertEqual(calculate_amount('150', '1200'), (150000, 1200, 180000))
        self.assertEqual(calculate_amount('0.125', '1200'), (125, 1200, 150))
        for quantity, price in [('0','1200'), ('-1','1200'), ('NaN','1200'), ('Infinity','1200'),
                                ('1','-1'), ('1','1.5'), ('0.0001','1200'), ('0.001','1201')]:
            with self.subTest(quantity=quantity, price=price), self.assertRaises(ValueError):
                calculate_amount(quantity, price)


class WebTests(AioHTTPTestCase):
    async def get_application(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=test_database(self)
        seed(self.path, 'test-only-password')
        return create_app(self.path)

    async def test_homepage_and_security_headers(self):
        response = await self.client.get('/')
        self.assertEqual(response.status, 200)
        body = await response.text()
        self.assertIn('HARVESTSHIELD', body)
        self.assertIn('2,610', body)
        self.assertNotIn('Farmer 01', body)
        self.assertNotIn('scrypt$', body)
        self.assertIn("frame-ancestors 'none'", response.headers['Content-Security-Policy'])
        self.assertEqual(response.headers['Cache-Control'], 'no-store')

    async def test_health(self):
        response = await self.client.get('/health')
        self.assertEqual(response.status, 200)
        self.assertEqual((await response.json())['status'], 'ok')

    async def test_stylesheet_and_private_routes(self):
        response = await self.client.get('/static/style.css')
        self.assertEqual(response.status, 200)
        for path in ['/farmers/1', '/deliveries/1', '/admin', '/static/', '/static/database.py']:
            with self.subTest(path=path):
                self.assertIn((await self.client.get(path, allow_redirects=False)).status, [303, 403, 404])

    async def test_static_symlinks_do_not_expose_external_files(self):
        from app.main import BASE
        secret = Path(self.temp.name) / 'private.txt'
        secret.write_text('private-test-content')
        link = BASE / 'static' / 'test-external-link.txt'
        try:
            link.symlink_to(secret)
        except OSError:
            self.skipTest('Creating symlinks is unavailable on this platform')
        try:
            response = await self.client.get('/static/test-external-link.txt')
            self.assertEqual(response.status, 404)
        finally:
            link.unlink()

    async def test_empty_database_renders_zeroes(self):
        with connect(self.path) as db:
            db.execute('DELETE FROM deliveries')
            db.execute('DELETE FROM farmers')
        response = await self.client.get('/')
        self.assertEqual(response.status, 200)
        self.assertNotIn('2,610', await response.text())


if __name__ == '__main__':
    unittest.main()
