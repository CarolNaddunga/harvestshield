"""Create synthetic fixtures with a user-supplied, local demo password."""
import argparse
import getpass
import os
from app.database import seed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--database', default=os.environ.get('HARVESTSHIELD_DB', 'data/harvestshield.sqlite3'))
    args = parser.parse_args()
    password = getpass.getpass('Choose a local demo password (12+ characters): ')
    if len(password) < 12:
        parser.error('Use at least 12 characters; do not reuse a real password.')
    changed = seed(args.database, password)
    print('Created 10 farmers, 2 clerks, 1 administrator and 18 deliveries.' if changed else 'Database already populated; nothing changed.')
    print('Accounts: farmer01..farmer10, clerk01, clerk02, admin. Sign in at /login.')


if __name__ == '__main__':
    main()
