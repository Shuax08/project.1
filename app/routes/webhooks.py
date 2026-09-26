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
    token=current_app.config.get('WHATSAPP_VERIFY_TOKEN','')
    if token and request.args.get('hub.mode')=='subscribe' and hmac.compare_digest(request.args.get('hub.verify_token',''),token): return request.args.get('hub.challenge','')
    return jsonify(error='verification failed'),403
@webhooks.post('/whatsapp')
def receive():
    if not valid_signature(request.get_data()): return jsonify(error='invalid signature'),401
    # Meta webhook payloads do not contain a trusted shop_id. Resolve the tenant
    # from a configured phone number ID before processing any customer action.
    return jsonify(error='WhatsApp phone number mapping is not configured'),503
