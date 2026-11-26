import tempfile
import unittest
from app.auth import verify_password
from app.database import connect
from scripts.serve import bootstrap
from storage_support import test_database

class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path=test_database(self)

    def test_hosted_passwords_are_explicit_and_not_reset(self):
        admin='synthetic-admin-password-only'
        clerk='synthetic-clerk-password-only'
        self.assertTrue(bootstrap(self.path,admin,clerk))
        with connect(self.path) as db:
            rows=db.execute('SELECT username,role,password_hash FROM users').fetchall()
            for row in rows:
                if row['role']=='admin': self.assertTrue(verify_password(admin,row['password_hash']))
                elif row['role']=='clerk': self.assertTrue(verify_password(clerk,row['password_hash']))
                else:
                    self.assertFalse(verify_password(admin,row['password_hash']))
                    self.assertFalse(verify_password(clerk,row['password_hash']))
                self.assertFalse(verify_password('preview-only-password',row['password_hash']))
        self.assertFalse(bootstrap(self.path,'a-different-admin-secret','a-different-clerk-secret'))
        with connect(self.path) as db:
            self.assertTrue(verify_password(admin,db.execute("SELECT password_hash FROM users WHERE username='admin'").fetchone()[0]))

    def test_missing_or_shared_hosted_passwords_leave_database_empty(self):
        for admin,clerk in [('', ''),('too-short','long-clerk-secret-here'),('shared-secret-password','shared-secret-password')]:
            with self.subTest(admin_length=len(admin)), self.assertRaises(ValueError): bootstrap(self.path,admin,clerk)
        with connect(self.path) as db: self.assertEqual(db.execute('SELECT COUNT(*) FROM users').fetchone()[0],0)
