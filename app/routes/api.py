from flask import Blueprint, request, jsonify, session
from decimal import Decimal, InvalidOperation
import secrets
from sqlalchemy import func
from app.models import db, Shop, User, Customer, MenuItem, Order, OrderItem, CreditAccount, CreditTransaction, PrinterSettings, AuditLog
from app.auth.decorators import login_required, roles
from app.services.geo import safe_zone
from app.services.receipt_service import build_receipt_data, render_receipt_text, render_receipt_html
from app.services.order_service import cancel_order
api=Blueprint('api',__name__)

def money(v):
    try: return Decimal(str(v)).quantize(Decimal('0.01'))
    except (InvalidOperation,TypeError): raise ValueError('invalid price')

@api.post('/auth/login')
def login():
    data=request.get_json(silent=True) or {}; user=User.query.filter_by(email=data.get('email')).first()
    if not user or not user.active or not user.check_password(data.get('password','')): return jsonify(error='invalid credentials'),401
    session.clear(); session['user_id']=user.id; session['csrf_token']=secrets.token_urlsafe(32)
    return jsonify(user_id=user.id,shop_id=user.shop_id,role=user.role,csrf_token=session['csrf_token'])
@api.post('/auth/logout')
def logout(): session.clear(); return jsonify(ok=True)
@api.post('/shops')
@login_required
@roles('PLATFORM_ADMIN')
def create_shop(user):
    d=request.get_json() or {}; slug=str(d.get('slug','')).lower()
    if not slug or not slug.replace('-','').isalnum() or Shop.query.filter_by(slug=slug).first(): return jsonify(error='invalid or duplicate slug'),400
    shop=Shop(name=d.get('name',''),slug=slug,phone=d.get('phone'),address=d.get('address')); db.session.add(shop); db.session.commit(); return jsonify(id=shop.id,slug=shop.slug),201
@api.get('/shops/me')
@login_required
def shop_me(user):
    if user.shop_id is None: return jsonify(error='platform user has no shop'),400
    return jsonify(id=user.shop_id, shop=Shop.query.get_or_404(user.shop_id).name)

@api.get('/customers')
@login_required
def customers(user):
    if user.shop_id is None: return jsonify(error='shop required'),400
    return jsonify(customers=[{'id':c.id,'name':c.name,'phone':c.phone,'address':c.address} for c in Customer.query.filter_by(shop_id=user.shop_id).order_by(Customer.id).limit(200)])

@api.post('/customers')
@login_required
def create_customer(user):
    d=request.get_json(silent=True) or {}; phone=str(d.get('phone','')).strip()
    if user.shop_id is None or not phone or len(phone)>40: return jsonify(error='invalid customer'),400
    existing=Customer.query.filter_by(shop_id=user.shop_id,phone=phone).first()
    if existing: return jsonify(id=existing.id,duplicate=True)
    c=Customer(shop_id=user.shop_id,phone=phone,name=str(d.get('name','')).strip()[:160],address=str(d.get('address','')).strip()[:255])
    db.session.add(c); db.session.commit(); return jsonify(id=c.id),201

@api.get('/customers/<int:customer_id>')
@login_required
def customer_detail(user,customer_id):
    c=Customer.query.filter_by(id=customer_id,shop_id=user.shop_id).first_or_404()
    return jsonify(id=c.id,name=c.name,phone=c.phone,address=c.address)

@api.post('/customers/<int:customer_id>/credit')
@login_required
@roles('SHOP_OWNER','SHOP_MANAGER')
def credit_transaction(user,customer_id):
    c=Customer.query.filter_by(id=customer_id,shop_id=user.shop_id).first_or_404()
    d=request.get_json(silent=True) or {}; kind=d.get('kind')
    if kind not in ('enable','charge','repayment'): return jsonify(error='invalid transaction'),400
    account=CreditAccount.query.filter_by(shop_id=user.shop_id,customer_id=c.id).first()
    if kind=='enable':
        if account is None: account=CreditAccount(shop_id=user.shop_id,customer_id=c.id,outstanding_balance=0)
        try: limit=money(d.get('limit',500))
        except ValueError: return jsonify(error='invalid limit'),400
        if not limit.is_finite() or limit<0: return jsonify(error='invalid limit'),400
        account.credit_enabled=True; account.credit_limit=limit; db.session.add(account)
    else:
        if not account or not account.credit_enabled: return jsonify(error='credit disabled'),400
        try: amount=money(d.get('amount'))
        except ValueError: return jsonify(error='invalid amount'),400
        if not amount.is_finite() or amount<=0: return jsonify(error='invalid amount'),400
        balance=Decimal(account.outstanding_balance or 0)
        if kind=='charge' and balance+amount>account.credit_limit: return jsonify(error='credit limit exceeded'),400
        if kind=='repayment' and amount>balance: return jsonify(error='repayment exceeds balance'),400
        if kind=='charge':
            o=Order.query.filter_by(id=d.get('order_id'),shop_id=user.shop_id,customer_id=c.id).first()
            if not o or o.total!=amount or o.payment_status!='UNPAID': return jsonify(error='invalid order charge'),400
            o.payment_status='PAID'; o.payment_method='CREDIT'
        else: o=None
        account.outstanding_balance=balance+amount if kind=='charge' else balance-amount
        db.session.add(CreditTransaction(account_id=account.id,kind=kind,amount=amount,order_id=o.id if o else None))
    db.session.add(AuditLog(shop_id=user.shop_id,actor_id=user.id,action='credit_'+kind,details={'customer_id':c.id}))
    db.session.commit(); return jsonify(balance=str(account.outstanding_balance),limit=str(account.credit_limit))

@api.get('/customers/<int:customer_id>/credit')
@login_required
def credit_history(user,customer_id):
    Customer.query.filter_by(id=customer_id,shop_id=user.shop_id).first_or_404()
    account=CreditAccount.query.filter_by(shop_id=user.shop_id,customer_id=customer_id).first()
    if not account: return jsonify(enabled=False,balance='0.00',transactions=[])
    return jsonify(enabled=account.credit_enabled,balance=str(account.outstanding_balance),transactions=[{'id':t.id,'kind':t.kind,'amount':str(t.amount),'order_id':t.order_id} for t in CreditTransaction.query.filter_by(account_id=account.id).order_by(CreditTransaction.id).limit(200)])
@api.get('/menu')
@login_required
def menu(user): return jsonify(items=[item_json(x) for x in MenuItem.query.filter_by(shop_id=user.shop_id).order_by(MenuItem.sort_order,MenuItem.id)])
@api.post('/menu')
@login_required
@roles('PLATFORM_ADMIN','SHOP_OWNER','SHOP_MANAGER')
def add_menu(user):
    d=request.get_json() or {}
    try: price=money(d['price'])
    except (KeyError,ValueError): return jsonify(error='invalid price'),400
    if not price.is_finite() or price<0 or not str(d.get('name','')).strip() or user.shop_id is None: return jsonify(error='invalid item'),400
    x=MenuItem(shop_id=user.shop_id,name=str(d.get('name','')).strip(),description=d.get('description'),category=d.get('category'),price=price,image_url=d.get('image_url'),available=bool(d.get('available',True)),sort_order=int(d.get('sort_order',0))); db.session.add(x); db.session.commit(); return jsonify(item_json(x)),201
@api.patch('/menu/<int:item_id>')
@login_required
@roles('PLATFORM_ADMIN','SHOP_OWNER','SHOP_MANAGER')
def edit_menu(user,item_id):
    x=MenuItem.query.filter_by(id=item_id,shop_id=user.shop_id).first_or_404(); d=request.get_json() or {}
    for k in ('name','description','category','image_url','available','sort_order'):
        if k in d: setattr(x,k,d[k])
    if 'price' in d:
        try:
            x.price=money(d['price'])
            if not x.price.is_finite() or x.price<0: raise ValueError()
        except ValueError: return jsonify(error='invalid price'),400
    db.session.commit(); return jsonify(item_json(x))
@api.post('/orders')
@login_required
def create_order(user):
    d=request.get_json() or {}; key=request.headers.get('Idempotency-Key') or d.get('idempotency_key')
    if key:
        old=Order.query.filter_by(shop_id=user.shop_id,idempotency_key=key).first()
        if old: return jsonify(order=order_json(old),duplicate=True)
    customer=Customer.query.filter_by(id=d.get('customer_id'),shop_id=user.shop_id).first()
    if not customer: return jsonify(error='customer not found'),404
    lines=d.get('items',[])
    if not isinstance(lines,list) or not lines or len(lines)>20: return jsonify(error='invalid cart'),400
    order=Order(shop_id=user.shop_id,customer_id=customer.id,idempotency_key=key); total=Decimal('0')
    for line in lines:
        if not isinstance(line,dict): return jsonify(error='invalid cart'),400
        try: qty=int(line.get('quantity',0))
        except (ValueError,TypeError): return jsonify(error='invalid quantity'),400
        item=MenuItem.query.filter_by(id=line.get('item_id'),shop_id=user.shop_id).first()
        if not item or not item.available or qty<1 or qty>50: return jsonify(error='invalid item or quantity'),400
        amount=item.price*qty; total+=amount
        order.items.append(OrderItem(menu_item_id=item.id,item_name=item.name,unit_price=item.price,quantity=qty,line_total=amount))
    order.subtotal=total; order.total=total; db.session.add(order); db.session.commit(); return jsonify(order=order_json(order)),201
@api.get('/orders/<int:order_id>')
@login_required
def get_order(user,order_id):
    o=Order.query.filter_by(id=order_id,shop_id=user.shop_id).first_or_404(); return jsonify(order=order_json(o))
@api.patch('/orders/<int:order_id>')
@login_required
@roles('PLATFORM_ADMIN','SHOP_OWNER','SHOP_MANAGER','SHOP_STAFF')
def update_order(user,order_id):
    o=Order.query.filter_by(id=order_id,shop_id=user.shop_id).first_or_404(); d=request.get_json() or {}
    if 'status' in d and d['status'] not in ('Pending','Confirmed','Preparing','Ready','Delivered','Cancelled'): return jsonify(error='invalid status'),400
    if 'status' in d:
        if d['status']=='Cancelled':
            try: cancel_order(o)
            except ValueError as exc: return jsonify(error=str(exc)),400
        else: o.status=d['status']
    if 'payment_status' in d: return jsonify(error='payment status requires a verified payment or ledger transaction'),400
    db.session.commit(); return jsonify(order=order_json(o))
@api.get('/orders/<int:order_id>/receipt')
@login_required
def receipt(user,order_id):
    o=Order.query.filter_by(id=order_id,shop_id=user.shop_id).first_or_404(); return jsonify(build_receipt_data(o))
@api.get('/orders/<int:order_id>/receipt.html')
@login_required
def receipt_html(user,order_id):
    o=Order.query.filter_by(id=order_id,shop_id=user.shop_id).first_or_404(); return render_receipt_html(build_receipt_data(o))
@api.get('/shops/me/printer')
@login_required
def printer_get(user):
    p=PrinterSettings.query.filter_by(shop_id=user.shop_id).first(); return jsonify(enabled=p.enabled if p else False,host=p.host if p else None,port=p.port if p else 9100)
@api.patch('/shops/me/printer')
@login_required
@roles('PLATFORM_ADMIN','SHOP_OWNER','SHOP_MANAGER')
def printer_patch(user):
    p=PrinterSettings.query.filter_by(shop_id=user.shop_id).first() or PrinterSettings(shop_id=user.shop_id); d=request.get_json() or {}; p.enabled=bool(d.get('enabled',p.enabled)); p.host=d.get('host',p.host); p.port=int(d.get('port',9100)); db.session.add(p); db.session.commit(); return jsonify(enabled=p.enabled,host=p.host,port=p.port)
@api.get('/reports')
@login_required
def reports(user):
    q=Order.query.filter_by(shop_id=user.shop_id); return jsonify(order_count=q.count(),sales=str(q.with_entities(func.coalesce(func.sum(Order.total),0)).scalar()),statuses={s:q.filter_by(status=s).count() for s in ('Pending','Confirmed','Preparing','Ready','Delivered','Cancelled')})

def item_json(x): return {'id':x.id,'name':x.name,'description':x.description,'category':x.category,'price':str(x.price),'image_url':x.image_url,'available':x.available,'sort_order':x.sort_order}
def order_json(o): return {'id':o.id,'shop_id':o.shop_id,'customer_id':o.customer_id,'status':o.status,'payment_status':o.payment_status,'payment_method':o.payment_method,'subtotal':str(o.subtotal),'total':str(o.total),'items':[{'name':i.item_name,'unit_price':str(i.unit_price),'quantity':i.quantity,'line_total':str(i.line_total)} for i in OrderItem.query.filter_by(order_id=o.id)]}
