from flask import Blueprint, request, jsonify, session
from decimal import Decimal, InvalidOperation
from sqlalchemy import func
from app.models import db, Shop, User, Customer, MenuItem, Order, OrderItem, CreditAccount, CreditTransaction, PrinterSettings
from app.auth.decorators import login_required, roles
from app.services.geo import safe_zone
from app.services.receipt_service import build_receipt_data, render_receipt_text, render_receipt_html
api=Blueprint('api',__name__)

def money(v):
    try: return Decimal(str(v)).quantize(Decimal('0.01'))
    except (InvalidOperation,TypeError): raise ValueError('invalid price')

@api.post('/auth/login')
def login():
    data=request.get_json(silent=True) or {}; user=User.query.filter_by(email=data.get('email')).first()
    if not user or not user.check_password(data.get('password','')): return jsonify(error='invalid credentials'),401
    session['user_id']=user.id; return jsonify(user_id=user.id,shop_id=user.shop_id,role=user.role)
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
def shop_me(user): return jsonify(id=user.shop_id, shop=Shop.query.get_or_404(user.shop_id).name)
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
    if price<0: return jsonify(error='invalid price'),400
    x=MenuItem(shop_id=user.shop_id,name=str(d.get('name','')).strip(),description=d.get('description'),category=d.get('category'),price=price,image_url=d.get('image_url'),available=bool(d.get('available',True)),sort_order=int(d.get('sort_order',0))); db.session.add(x); db.session.commit(); return jsonify(item_json(x)),201
@api.patch('/menu/<int:item_id>')
@login_required
@roles('PLATFORM_ADMIN','SHOP_OWNER','SHOP_MANAGER')
def edit_menu(user,item_id):
    x=MenuItem.query.filter_by(id=item_id,shop_id=user.shop_id).first_or_404(); d=request.get_json() or {}
    for k in ('name','description','category','image_url','available','sort_order'):
        if k in d: setattr(x,k,d[k])
    if 'price' in d:
        try: x.price=money(d['price'])
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
    if not lines or len(lines)>20: return jsonify(error='invalid cart'),400
    order=Order(shop_id=user.shop_id,customer_id=customer.id,idempotency_key=key); total=Decimal('0')
    for line in lines:
        qty=int(line.get('quantity',0)); item=MenuItem.query.filter_by(id=line.get('item_id'),shop_id=user.shop_id).first()
        if not item or not item.available or qty<1 or qty>50: return jsonify(error='invalid item or quantity'),400
        amount=item.price*qty; total+=amount; order.items=[] if False else None
        db.session.add(OrderItem(order=order,menu_item_id=item.id,item_name=item.name,unit_price=item.price,quantity=qty,line_total=amount))
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
    if 'status' in d: o.status=d['status']
    if 'payment_status' in d and d['payment_status'] in ('UNPAID','PENDING','PAID','FAILED','REFUNDED'): o.payment_status=d['payment_status']
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
