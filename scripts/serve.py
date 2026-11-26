"""Container entry point. Hosted state lives in PostgreSQL, never the image."""
import os
import secrets
from app.auth import hash_password
from app.database import connect, initialize, seed
from app.main import main

def bootstrap(url,admin_password,clerk_password):
    initialize(url)
    with connect(url) as db:
        exists=db.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    if exists:
        return False
    if len(admin_password)<16 or len(clerk_password)<16 or admin_password==clerk_password:
        raise ValueError('Set distinct administrator and clerk passwords of at least 16 characters in the hosting environment.')
    # Fixture accounts never receive any known development password.
    seed(url,secrets.token_urlsafe(48))
    with connect(url) as db:
        db.execute("UPDATE users SET password_hash=? WHERE username='admin'",(hash_password(admin_password),))
        db.execute("UPDATE users SET password_hash=? WHERE role='clerk'",(hash_password(clerk_password),))
    return True

if __name__=='__main__':
    url=os.environ.get('DATABASE_URL')
    if os.environ.get('RENDER')=='true' and not url:
        raise SystemExit('DATABASE_URL is required for hosted persistent storage.')
    if url:
        if not url.startswith(('postgresql://','postgres://')):
            raise SystemExit('Hosted DATABASE_URL must be PostgreSQL.')
        bootstrap(url,os.environ.get('HARVESTSHIELD_ADMIN_PASSWORD',''),os.environ.get('HARVESTSHIELD_CLERK_PASSWORD',''))
    main()
