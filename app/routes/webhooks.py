import hashlib
import hmac
from flask import Blueprint, request, jsonify, current_app
from app.models import db, WhatsAppChannel, IncomingMessage, OwnerWhatsAppIdentity, Shop, User, Order
from app.bot.customer import handle_customer
from app.bot.owner import handle_owner
from app.services.whatsapp_service import send_text, WhatsAppDeliveryError

webhooks = Blueprint('webhooks', __name__)


def valid_signature(raw):
    secret = current_app.config.get('WHATSAPP_APP_SECRET', '')
    supplied = request.headers.get('X-Hub-Signature-256', '')
    if not secret or not supplied.startswith('sha256='):
        return False
    expected = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, supplied[7:])


@webhooks.get('/whatsapp')
def verify():
    token = current_app.config.get('WHATSAPP_VERIFY_TOKEN', '')
    if token and request.args.get('hub.mode') == 'subscribe' and hmac.compare_digest(request.args.get('hub.verify_token', ''), token):
        return request.args.get('hub.challenge', '')
    return jsonify(error='verification failed'), 403


@webhooks.post('/whatsapp')
def receive():
    raw = request.get_data()
    if len(raw) > 256_000:
        return jsonify(error='payload too large'), 413
    if not valid_signature(raw):
        return jsonify(error='invalid signature'), 401
    payload = request.get_json(silent=True) or {}
    if payload.get('object') != 'whatsapp_business_account':
        return jsonify(ok=True)
    for entry in payload.get('entry', []):
        for change in entry.get('changes', []):
            if change.get('field') != 'messages':
                continue
            value = change.get('value') or {}
            phone_id = str((value.get('metadata') or {}).get('phone_number_id', ''))
            channel = WhatsAppChannel.query.filter_by(phone_number_id=phone_id).first()
            if not channel:
                continue
            shop = db.session.get(Shop, channel.shop_id)
            if not shop or shop.status != 'active':
                continue
            for message in value.get('messages', []):
                message_id = str(message.get('id', ''))
                sender = str(message.get('from', ''))
                if not message_id or not sender.isdigit() or len(sender) > 40:
                    continue
                record = IncomingMessage.query.filter_by(message_id=message_id).first()
                if record is None:
                    record = IncomingMessage(shop_id=shop.id, message_id=message_id, recipient=sender)
                    db.session.add(record)
                    try:
                        identity = OwnerWhatsAppIdentity.query.filter_by(shop_id=shop.id,phone=sender).first()
                        owner = db.session.get(User, identity.user_id) if identity else None
                        record.response = ((handle_owner(shop, owner, message) if owner else 'Owner access denied.') if identity
                                           else handle_customer(shop, sender, message, on_order=lambda order_id: setattr(record,'order_id',order_id)))
                        db.session.commit()
                    except Exception:
                        db.session.rollback()
                        raise
                if not record.sent and record.response:
                    try:
                        send_text(channel.phone_number_id, sender, record.response)
                    except WhatsAppDeliveryError:
                        current_app.logger.warning('WhatsApp delivery failed for message id %s', message_id)
                        return jsonify(error='message delivery unavailable'), 503
                    record.sent = True
                    db.session.commit()
                if record.order_id and not record.owner_notified:
                    owner_identity = OwnerWhatsAppIdentity.query.filter_by(shop_id=shop.id).order_by(OwnerWhatsAppIdentity.id).first()
                    if owner_identity:
                        linked_user = db.session.get(User, owner_identity.user_id)
                        if linked_user and linked_user.active and linked_user.role in ('SHOP_OWNER','SHOP_MANAGER'):
                            order = Order.query.filter_by(id=record.order_id,shop_id=shop.id).first()
                            try:
                                send_text(channel.phone_number_id,owner_identity.phone,
                                          f'New order #{order.id}: AED {order.total:.2f}. Send ORDER {order.id} or ACCEPT {order.id}.')
                            except WhatsAppDeliveryError:
                                current_app.logger.warning('Owner notification failed for message id %s',message_id)
                                return jsonify(error='owner notification unavailable'),503
                    record.owner_notified=True
                    db.session.commit()
    return jsonify(ok=True)
