"""Cooperative overview and authenticated portal entry point."""
import argparse
import logging
import os
from decimal import Decimal
from html import escape
from pathlib import Path
from string import Template
from aiohttp import web
from .database import initialize, overview
from .portal import register

BASE = Path(__file__).parent
DB_KEY = web.AppKey("database_path", str)


@web.middleware
async def security_headers(request, handler):
    error = None
    try:
        response = await handler(request)
    except web.HTTPException as exc:
        response = exc
        error = exc
    response.headers.update({
        "Content-Security-Policy": "default-src 'none'; style-src 'self'; img-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "no-referrer",
        "Cache-Control": "no-store",
        "X-Frame-Options": "DENY",
    })
    if error is not None:
        raise error
    return response


async def home(request):
    totals, crops = overview(request.app[DB_KEY])
    crop_rows = ''.join(
        f'<div class="crop-row"><span class="crop-symbol">{escape(c["crop"][:1].upper())}</span>'
        f'<div><strong>{escape(c["crop"].title())}</strong><small>{c["count"]} deliveries</small></div>'
        f'<b>{Decimal(c["grams"]) / 1000:,.0f}<small>kg collected</small></b></div>' for c in crops)
    values = dict(farmers=f'{totals["farmers"]:,}', deliveries=f'{totals["deliveries"]:,}',
                  kilograms=f'{Decimal(totals["quantity_grams"]) / 1000:,.0f}',
                  approved=f'{totals["approved_ugx"]:,}', pending=str(totals['pending']), crop_rows=crop_rows)
    html = Template((BASE / 'templates/home.html').read_text()).substitute(values)
    return web.Response(text=html, content_type='text/html')


async def health(request):
    overview(request.app[DB_KEY])
    return web.json_response({'status': 'ok', 'phase': 'core-portal'})


def create_app(database_path=None):
    path = str(database_path or os.environ.get('DATABASE_URL') or os.environ.get('HARVESTSHIELD_DB', 'data/harvestshield.sqlite3'))
    initialize(path)
    app = web.Application(middlewares=[security_headers], client_max_size=64*1024)
    app[DB_KEY] = path
    register(app, path)
    app.router.add_get('/', home)
    app.router.add_get('/health', health)
    app.router.add_static('/static/', BASE / 'static', follow_symlinks=False, show_index=False)
    return app


def main():
    parser = argparse.ArgumentParser(description='HARVESTSHIELD local foundation preview')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=int(os.environ.get('PORT', '8080')))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    web.run_app(create_app(), host=args.host, port=args.port)


if __name__ == '__main__':
    main()
