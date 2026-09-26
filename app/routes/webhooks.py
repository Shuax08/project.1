import hashlib,hmac,time
from flask import Blueprint,request,jsonify,current_app
from app.models import db, Shop, BotSession
webhooks=Blueprint('webhooks',__name__)
def valid_signature(raw):
    secret=current_app.config.get('WHATSAPP_APP_SECRET','')
    if not secret:return False
    supplied=request.headers.get('X-Hub-Signature-256','').removeprefix('sha256=')
    return hmac.compare_digest(hmac.new(secret.encode(),raw,hashlib.sha256).hexdigest(),supplied)
@webhooks.get('/whatsapp')
def verify():
    if request.args.get('hub.verify_token')==current_app.config['WHATSAPP_VERIFY_TOKEN']: return request.args.get('hub.challenge','')
    return jsonify(error='verification failed'),403
@webhooks.post('/whatsapp')
def receive():
    if not valid_signature(request.get_data()): return jsonify(error='invalid signature'),401
    payload=request.get_json(silent=True) or {}; shop=Shop.query.filter_by(id=payload.get('shop_id')).first()
    if not shop:return jsonify(error='ignored'),200
    phone=str(payload.get('from','')); s=BotSession.query.filter_by(shop_id=shop.id,phone=phone).first() or BotSession(shop_id=shop.id,phone=phone)
    s.state='received'; db.session.add(s); db.session.commit(); return jsonify(ok=True)
