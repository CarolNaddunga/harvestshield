"""Authenticated cooperative workflows with server-side sessions and permissions."""
import asyncio
import hashlib
import hmac
import json
import secrets
import re
import os
import sqlite3
import time
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from html import escape
from aiohttp import web
from .auth import verify_password, hash_password
from .database import connect
from .models import CROPS, calculate_amount

COOKIE = 'harvestshield_session'
DATABASE = web.AppKey('portal_database', str)
DUMMY_HASH = web.AppKey('dummy_password_hash', str)

def e(value):
    return escape(str(value), quote=True)

def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()

def event(db, actor, action, record=None, details=None):
    db.execute('INSERT INTO audit_events (occurred_at,actor_id,action,record_id,details) VALUES (?,?,?,?,?)',
               (datetime.now(timezone.utc).isoformat(),actor,action,record,json.dumps(details or {},sort_keys=True)))

def session(request, required=True):
    with connect(request.app[DATABASE]) as db:
        row=db.execute("SELECT s.*,u.username,u.display_name,u.role FROM sessions s LEFT JOIN users u ON u.id=s.user_id WHERE token_hash=? AND expires_at>?",(digest(request.cookies.get(COOKIE,'')),int(time.time()))).fetchone()
    if required and (row is None or row['user_id'] is None):
        raise web.HTTPSeeOther('/login')
    return dict(row) if row else None

def role(request, *allowed):
    user=session(request)
    if user['role'] not in allowed:
        with connect(request.app[DATABASE]) as db:
            event(db,user['user_id'],'access.denied',details={'path':request.path})
        raise web.HTTPForbidden(text='Your role cannot perform this action.')
    return user

def csrf(user, data):
    if not hmac.compare_digest(user['csrf'].encode(),str(data.get('csrf','')).encode()):
        raise web.HTTPForbidden(text='Form expired or invalid. Reload the page and try again.')

def token_field(user):
    return f'<input type="hidden" name="csrf" value="{e(user["csrf"])}">'

def new_session(db,user_id=None):
    token=secrets.token_urlsafe(32)
    db.execute('DELETE FROM sessions WHERE expires_at<=?',(int(time.time()),))
    db.execute('INSERT INTO sessions VALUES (?,?,?,?)',(digest(token),user_id,secrets.token_urlsafe(32),int(time.time())+(3600 if user_id else 900)))
    return token

def set_cookie(response,token,request):
    response.set_cookie(COOKIE,token,httponly=True,samesite='Strict',secure=request.scheme=='https' or os.environ.get('HARVESTSHIELD_SECURE_COOKIES')=='1',max_age=3600,path='/')

def page(title,content,user=None,status=200):
    nav='<a href="/">Overview</a>'
    if user and user.get('user_id'):
        nav+='<a href="/portal">My workspace</a><a href="/deliveries">Deliveries</a><a href="/farmers">Farmers</a>'
        if user['role']=='admin': nav+='<a href="/audit">Integrity trail</a><a href="/users">Accounts</a>'
        nav+=f'<form method="post" action="/logout">{token_field(user)}<button class="quiet">Sign out</button></form>'
        identity=f'{e(user["display_name"])} · {e(user["role"].title())}'
    else:
        identity='GreenFields Produce Cooperative'
    return web.Response(status=status,content_type='text/html',text=f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(title)} · HARVESTSHIELD</title><link rel="stylesheet" href="/static/style.css"></head><body><a class="skip" href="#content">Skip to content</a><header class="portal-header"><a class="brand" href="/">HARVESTSHIELD</a><span>{identity}</span></header><nav class="portal-nav" aria-label="Portal navigation">{nav}</nav><main class="portal-main" id="content"><p class="eyebrow">GREENFIELDS / MEMBER PORTAL</p><h1>{e(title)}</h1>{content}<footer>Synthetic records only · Fictional amounts · No real payments</footer></main></body></html>""")

async def login(request):
    current=session(request,False)
    if current and current['user_id']: raise web.HTTPSeeOther('/portal')
    fresh=None
    if current is None:
        with connect(request.app[DATABASE]) as db:
            fresh=new_session(db)
            current=dict(db.execute('SELECT * FROM sessions WHERE token_hash=?',(digest(fresh),)).fetchone())
    error=''
    status=200
    if request.method=='POST':
        data=await request.post()
        csrf(current,data)
        username=str(data.get('username','')).strip()[:100]
        password=str(data.get('password',''))
        now=int(time.time())
        # Limit both account and network source; store only hashed identifiers.
        keys=[digest('account:'+username),digest('source:'+(request.remote or 'local'))]
        with connect(request.app[DATABASE]) as db:
            limited=False
            for key in keys:
                attempt=db.execute('SELECT * FROM login_attempts WHERE identity=?',(key,)).fetchone()
                if attempt and now-attempt['started_at']<300 and attempt['attempts']>=10: limited=True
                db.execute('INSERT INTO login_attempts VALUES (?,1,?) ON CONFLICT(identity) DO UPDATE SET attempts=CASE WHEN ?-login_attempts.started_at>=300 THEN 1 ELSE login_attempts.attempts+1 END,started_at=CASE WHEN ?-login_attempts.started_at>=300 THEN ? ELSE login_attempts.started_at END',(key,now,now,now,now))
            account=db.execute('SELECT * FROM users WHERE username=?',(username,)).fetchone()
        if limited:
            error='Too many attempts. Try again in five minutes.'; status=429
        else:
            # A fixed-cost dummy hash also covers unknown accounts.
            stored=account['password_hash'] if account else request.app[DUMMY_HASH]
            valid=await asyncio.to_thread(verify_password,password[:1024],stored)
            if account and valid and len(password)<=1024:
                with connect(request.app[DATABASE]) as db:
                    db.execute('DELETE FROM sessions WHERE token_hash=?',(digest(request.cookies.get(COOKIE,'')),))
                    db.execute('DELETE FROM login_attempts WHERE identity=?',(keys[0],))
                    token=new_session(db,account['id'])
                    event(db,account['id'],'auth.login')
                response=web.HTTPSeeOther('/portal'); set_cookie(response,token,request); raise response
            error='Username or password is incorrect.'; status=401
            with connect(request.app[DATABASE]) as db: event(db,None,'auth.failed')
    form=f"""<div class="login-grid"><section class="panel"><h2>Welcome back.</h2><p>Sign in to your cooperative workspace.</p><p class="error" role="alert">{e(error)}</p><form method="post" action="/login">{token_field(current)}<label>Username<input name="username" autocomplete="username" required maxlength="100"></label><label>Password<input type="password" name="password" autocomplete="current-password" required maxlength="1024"></label><button>Sign in</button></form><p class="hint">New to GreenFields? <a href="/register">Create an account</a>.</p></section><figure><img src="/static/images/harvesting-coffee.webp" alt="Coffee harvesting in Uganda"><figcaption>Photo: Jameswasswa · <a href="/#photo-credits">CC BY-SA 4.0 / credits</a>. Agricultural context; fictional cooperative.</figcaption></figure></div>"""
    response=page('Member sign-in',form,status=status)
    if fresh: set_cookie(response,fresh,request)
    return response

async def signup(request):
    current=session(request,False)
    if current and current['user_id']: raise web.HTTPSeeOther('/portal')
    fresh=None
    if current is None:
        with connect(request.app[DATABASE]) as db:
            fresh=new_session(db)
            current=dict(db.execute('SELECT * FROM sessions WHERE token_hash=?',(digest(fresh),)).fetchone())
    error=''; status=200; data={}
    if request.method=='POST':
        data=await request.post(); csrf(current,data)
        now=int(time.time()); key=digest('signup:'+(request.remote or 'local'))
        with connect(request.app[DATABASE]) as db:
            attempt=db.execute('SELECT * FROM login_attempts WHERE identity=?',(key,)).fetchone()
            limited=bool(attempt and now-attempt['started_at']<300 and attempt['attempts']>=10)
            db.execute('INSERT INTO login_attempts VALUES (?,1,?) ON CONFLICT(identity) DO UPDATE SET attempts=CASE WHEN ?-login_attempts.started_at>=300 THEN 1 ELSE login_attempts.attempts+1 END,started_at=CASE WHEN ?-login_attempts.started_at>=300 THEN ? ELSE login_attempts.started_at END',(key,now,now,now,now))
        if limited:
            error='Too many registration attempts. Please try again in five minutes.'; status=429
        else:
            username=str(data.get('username','')).strip().lower()
            name=str(data.get('display_name','')).strip()
            district=str(data.get('district','')).strip()
            password=str(data.get('password',''))
            confirmation=str(data.get('confirm_password',''))
            if not re.fullmatch(r'[a-z][a-z0-9_]{2,31}',username):
                error='Use a username of 3–32 letters, numbers or underscores, starting with a letter.'
            elif not 2<=len(name)<=80 or any(ord(c)<32 for c in name):
                error='Enter a display name between 2 and 80 characters.'
            elif not 2<=len(district)<=60 or any(ord(c)<32 for c in district):
                error='Enter a district between 2 and 60 characters.'
            elif not 12<=len(password)<=128:
                error='Choose a password between 12 and 128 characters.'
            elif password!=confirmation:
                error='The passwords do not match.'
            if error:
                status=400
            else:
                password_hash=await asyncio.to_thread(hash_password,password)
                try:
                    with connect(request.app[DATABASE]) as db:
                        cur=db.execute("INSERT INTO users (username,display_name,role,password_hash) VALUES (?,?,'farmer',?)",(username,name,password_hash))
                        user_id=cur.lastrowid
                        db.execute('INSERT INTO farmers (user_id,member_code,district) VALUES (?,?,?)',(user_id,f'GF-{user_id:05}',district))
                        event(db,user_id,'account.created',details={'role':'farmer'})
                        db.execute('DELETE FROM sessions WHERE token_hash=?',(digest(request.cookies.get(COOKIE,'')),))
                        new_token=new_session(db,user_id)
                    response=web.HTTPSeeOther('/portal'); set_cookie(response,new_token,request); raise response
                except sqlite3.IntegrityError:
                    error='That username is already taken. Please choose another.'; status=409
    form=f"""<div class="login-grid registration-grid"><section class="panel"><h2>Your next harvest starts here.</h2><p>Create your farmer account to view your produce deliveries and approval status.</p><p class="error" role="alert">{e(error)}</p><form method="post" action="/register">{token_field(current)}<label>Display name<input name="display_name" autocomplete="nickname" required minlength="2" maxlength="80" value="{e(data.get('display_name',''))}"></label><label>District<input name="district" autocomplete="address-level2" required minlength="2" maxlength="60" value="{e(data.get('district',''))}"></label><label>Username<input name="username" autocomplete="username" required minlength="3" maxlength="32" pattern="[A-Za-z][A-Za-z0-9_]*" value="{e(data.get('username',''))}" aria-describedby="username-help"></label><small id="username-help">3–32 letters, numbers or underscores, starting with a letter.</small><label>Password<input type="password" name="password" autocomplete="new-password" required minlength="12" maxlength="128" aria-describedby="password-help"></label><small id="password-help">Use 12–128 characters and a password you do not use elsewhere.</small><label>Confirm password<input type="password" name="confirm_password" autocomplete="new-password" required minlength="12" maxlength="128"></label><button>Create account</button></form><p class="hint">Already a member? <a href="/login">Sign in</a>.</p></section><figure><img src="/static/images/beans-garden.webp" alt="Agricultural work in a bean garden in Uganda"><figcaption>Photo: Emmanuel Ssekaggo · <a href="/#photo-credits">CC BY-SA 4.0 / credits</a>. Agricultural context; fictional cooperative.</figcaption><div class="registration-message"><p class="eyebrow">GROWING TOGETHER</p><h2>One account.<br>A clearer harvest.</h2><p>Follow your deliveries, quantities and approval decisions in one place.</p></div></figure></div>"""
    response=page('Create an account',form,status=status)
    if fresh: set_cookie(response,fresh,request)
    return response

async def logout(request):
    user=session(request); csrf(user,await request.post())
    with connect(request.app[DATABASE]) as db:
        db.execute('DELETE FROM sessions WHERE token_hash=?',(digest(request.cookies.get(COOKIE,'')),))
        event(db,user['user_id'],'auth.logout')
    response=web.HTTPSeeOther('/login'); response.del_cookie(COOKIE,path='/'); raise response

def scoped_deliveries(db,user,query=''):
    where=[]; args=[]
    if user['role']=='farmer': where.append('f.user_id=?'); args.append(user['user_id'])
    if query:
        where.append('(u.display_name LIKE ? OR d.crop LIKE ? OR f.member_code LIKE ?)'); args.extend(['%'+query+'%']*3)
    sql='SELECT d.*,u.display_name,f.member_code FROM deliveries d JOIN farmers f ON f.id=d.farmer_id JOIN users u ON u.id=f.user_id'
    if where: sql+=' WHERE '+' AND '.join(where)
    return db.execute(sql+' ORDER BY d.id DESC',args).fetchall()

def delivery_table(rows):
    body=''.join(f'<tr><td><a href="/deliveries/{x["id"]}">GF-D{x["id"]:04}</a></td><td>{e(x["display_name"])}</td><td>{e(x["crop"].title())}</td><td>{Decimal(x["quantity_grams"])/1000:,.3f}</td><td>{x["amount_ugx"]:,}</td><td><span class="pill">{e(x["status"])}</span></td></tr>' for x in rows)
    return '<div class="table-wrap"><table><thead><tr><th>Delivery</th><th>Farmer</th><th>Crop</th><th>Kg</th><th>Amount (UGX)</th><th>Status</th></tr></thead><tbody>'+(body or '<tr><td colspan="6">No deliveries found.</td></tr>')+'</tbody></table></div>'

async def dashboard(request):
    user=session(request)
    with connect(request.app[DATABASE]) as db: rows=scoped_deliveries(db,user)
    amount=sum(x['amount_ugx'] for x in rows if x['status']=='approved')
    kg=Decimal(sum(x['quantity_grams'] for x in rows))/1000
    pending=sum(x['status']=='pending' for x in rows)
    cards=f'<section class="stats"><article><span>Visible deliveries</span><strong>{len(rows)}</strong></article><article><span>Produce collected (kg)</span><strong>{kg:,.3f}</strong></article><article><span>Approved UGX</span><strong>{amount:,}</strong></article><article><span>Pending review</span><strong>{pending}</strong></article></section>'
    action='<a class="action" href="/deliveries/new">Record a delivery</a>' if user['role'] in ('clerk','admin') else '<p class="hint">You can view only your own profile and deliveries.</p>'
    return page('Your cooperative workspace',cards+action+'<h2>Recent deliveries</h2>'+delivery_table(rows[:10]),user)

async def deliveries(request):
    user=session(request); q=request.query.get('q','')[:100]
    with connect(request.app[DATABASE]) as db: rows=scoped_deliveries(db,user,q)
    form=f'<form method="get" class="search"><label>Search farmer or crop<input name="q" value="{e(q)}" maxlength="100"></label><button>Search</button></form>'
    return page('Produce deliveries',form+delivery_table(rows),user)

async def farmers(request):
    user=session(request)
    with connect(request.app[DATABASE]) as db:
        sql='SELECT f.*,u.display_name FROM farmers f JOIN users u ON u.id=f.user_id'
        rows=db.execute(sql+(' WHERE f.user_id=?' if user['role']=='farmer' else '') ,(user['user_id'],) if user['role']=='farmer' else ()).fetchall()
    content=''.join(f'<article class="panel"><h2><a href="/farmers/{x["id"]}">{e(x["display_name"])}</a></h2><p>{e(x["member_code"])} · {e(x["district"])}</p></article>' for x in rows)
    return page('Your profile' if user['role']=='farmer' else 'Cooperative farmers','<div class="member-grid">'+content+'</div>',user)

async def farmer_detail(request):
    user=session(request)
    with connect(request.app[DATABASE]) as db:
        farmer=db.execute('SELECT f.*,u.display_name FROM farmers f JOIN users u ON u.id=f.user_id WHERE f.id=?',(int(request.match_info['id']),)).fetchone()
        if farmer is None: raise web.HTTPNotFound()
        if user['role']=='farmer' and farmer['user_id']!=user['user_id']:
            raise web.HTTPForbidden(text='You may only view your own farmer profile.')
        rows=[x for x in scoped_deliveries(db,user) if x['farmer_id']==farmer['id']]
    return page(farmer['display_name'],f'<p>{e(farmer["member_code"])} · {e(farmer["district"])}</p>'+delivery_table(rows),user)

async def delivery_detail(request):
    user=session(request); record=int(request.match_info['id'])
    with connect(request.app[DATABASE]) as db:
        item=db.execute('SELECT d.*,f.user_id,u.display_name FROM deliveries d JOIN farmers f ON f.id=d.farmer_id JOIN users u ON u.id=f.user_id WHERE d.id=?',(record,)).fetchone()
        if item is None: raise web.HTTPNotFound()
        if user['role']=='farmer' and item['user_id']!=user['user_id']:
            event(db,user['user_id'],'access.denied',record,{'path':request.path})
            # Commit the denial record before raising an HTTP error.
            db.commit()
            raise web.HTTPForbidden(text='You may only view your own deliveries.')
    content=f'<section class="panel"><h2>{e(item["crop"].title())} delivery</h2><dl>'
    for name,value in [('Farmer',item['display_name']),('Quantity (kg)',Decimal(item['quantity_grams'])/1000),('Unit price (UGX)',item['unit_price_ugx']),('Amount (UGX)',f'{item["amount_ugx"]:,}'),('Delivered at',item['delivered_at']),('Status',item['status'])]:
        content+=f'<dt>{e(name)}</dt><dd>{e(value)}</dd>'
    content+='</dl>'
    if user['role']=='admin':
        content+=f'<form method="post" action="/deliveries/{record}/status">{token_field(user)}<input type="hidden" name="expected_status" value="{e(item["status"])}"><label>Approval decision<select name="status"><option value="approved">Approve</option><option value="rejected">Reject</option></select></label><button>Save decision</button></form>'
    return page(f'Delivery GF-D{record:04}',content+'</section>',user)

async def new_delivery(request):
    user=role(request,'clerk','admin'); error=''; status=200
    data={}
    if request.method=='POST':
        data=await request.post(); csrf(user,data)
        try:
            farmer_id=int(data.get('farmer_id',''))
            crop=str(data.get('crop',''))
            if crop not in CROPS: raise ValueError('Choose a supported crop.')
            grams,price,amount=calculate_amount(data.get('quantity',''),CROPS[crop])
            delivered=date.fromisoformat(str(data.get('date','')))
            if delivered>datetime.now(timezone(timedelta(hours=3))).date(): raise ValueError('Delivery date cannot be in the future.')
            with connect(request.app[DATABASE]) as db:
                if not db.execute('SELECT id FROM farmers WHERE id=?',(farmer_id,)).fetchone(): raise ValueError('Choose an existing farmer.')
                cur=db.execute("INSERT INTO deliveries (farmer_id,crop,quantity_grams,unit_price_ugx,amount_ugx,delivered_at,recorded_by,status) VALUES (?,?,?,?,?,?,?,'pending')",(farmer_id,crop,grams,price,amount,delivered.isoformat(),user['user_id']))
                event(db,user['user_id'],'delivery.created',cur.lastrowid,{'farmer_id':farmer_id,'crop':crop,'quantity_grams':grams,'unit_price_ugx':price,'amount_ugx':amount,'status':'pending'})
                record=cur.lastrowid
            raise web.HTTPSeeOther(f'/deliveries/{record}')
        except (ValueError,TypeError) as exc:
            error=str(exc) or 'Enter valid delivery details.'; status=400
    with connect(request.app[DATABASE]) as db:
        members=db.execute('SELECT f.id,f.member_code,u.display_name FROM farmers f JOIN users u ON u.id=f.user_id ORDER BY f.id').fetchall()
    options=''.join(f'<option value="{x["id"]}"'+(' selected' if str(data.get('farmer_id',''))==str(x['id']) else '')+f'>{e(x["member_code"])} — {e(x["display_name"])}</option>' for x in members)
    crops=''.join(f'<option value="{c}"'+(' selected' if data.get('crop')==c else '')+f'>{c.title()} — UGX {v:,}/kg</option>' for c,v in CROPS.items())
    form=f'<section class="panel form-panel"><p>Approved crop prices are applied by the server. New records await administrator approval.</p><p class="error" role="alert">{e(error)}</p><form method="post">{token_field(user)}<label>Farmer<select name="farmer_id" required>{options}</select></label><label>Crop<select name="crop" required>{crops}</select></label><label>Quantity (kg)<input name="quantity" type="number" min="0.001" max="1000000" step="0.001" required value="{e(data.get("quantity",""))}"></label><label>Delivery date<input name="date" type="date" required value="{e(data.get("date",datetime.now(timezone(timedelta(hours=3))).date().isoformat()))}"></label><button>Record delivery</button></form></section>'
    return page('Record a delivery',form,user,status)

async def approval(request):
    user=role(request,'admin'); data=await request.post(); csrf(user,data)
    status=str(data.get('status','')); record=int(request.match_info['id'])
    if status not in ('approved','rejected'): raise web.HTTPBadRequest(text='Choose approved or rejected.')
    with connect(request.app[DATABASE]) as db:
        old=db.execute('SELECT status FROM deliveries WHERE id=?',(record,)).fetchone()
        if not old: raise web.HTTPNotFound()
        if old['status']!=data.get('expected_status'): raise web.HTTPConflict(text='Record changed. Reload before deciding.')
        if old['status']!=status:
            db.execute('UPDATE deliveries SET status=? WHERE id=?',(status,record))
            event(db,user['user_id'],'delivery.status_changed',record,{'changed_fields':{'status':{'before':old['status'],'after':status}}})
    raise web.HTTPSeeOther(f'/deliveries/{record}')

async def audit(request):
    user=role(request,'admin')
    with connect(request.app[DATABASE]) as db:
        rows=db.execute('SELECT a.*,u.username FROM audit_events a LEFT JOIN users u ON u.id=a.actor_id ORDER BY a.id DESC LIMIT 200').fetchall()
    content=''.join(f'<tr><td>{e(x["occurred_at"])}</td><td>{e(x["username"] or "system")}</td><td>{e(x["action"])}</td><td>{e(x["record_id"] or "—")}</td><td><pre>{e(x["details"])}</pre></td></tr>' for x in rows)
    return page('Produce integrity trail','<p>Latest 200 real application events. Timestamps retain their recorded offset (UTC for new events).</p><div class="table-wrap"><table><thead><tr><th>Time</th><th>Actor</th><th>Action</th><th>Record</th><th>Details</th></tr></thead><tbody>'+content+'</tbody></table></div>',user)

async def users(request):
    user=role(request,'admin')
    with connect(request.app[DATABASE]) as db: rows=db.execute('SELECT username,display_name,role FROM users ORDER BY id').fetchall()
    content=''.join(f'<tr><td>{e(x["username"])}</td><td>{e(x["display_name"])}</td><td>{e(x["role"])}</td></tr>' for x in rows)
    return page('Member accounts','<p>Read-only account directory. Farmers can register from the sign-in page; staff role editing is restricted.</p><div class="table-wrap"><table><thead><tr><th>Username</th><th>Name</th><th>Role</th></tr></thead><tbody>'+content+'</tbody></table></div>',user)

def register(app,path):
    from .auth import hash_password
    app[DATABASE]=path
    app[DUMMY_HASH]=hash_password(secrets.token_urlsafe(32))
    app.router.add_get('/register',signup); app.router.add_post('/register',signup)
    app.router.add_get('/login',login); app.router.add_post('/login',login)
    app.router.add_post('/logout',logout)
    app.router.add_get('/portal',dashboard)
    app.router.add_get('/deliveries',deliveries)
    app.router.add_get('/deliveries/new',new_delivery); app.router.add_post('/deliveries/new',new_delivery)
    app.router.add_get('/deliveries/{id:[0-9]+}',delivery_detail)
    app.router.add_post('/deliveries/{id:[0-9]+}/status',approval)
    app.router.add_get('/farmers',farmers); app.router.add_get('/farmers/{id:[0-9]+}',farmer_detail)
    app.router.add_get('/audit',audit); app.router.add_get('/users',users)
