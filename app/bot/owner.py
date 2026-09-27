"""Owner commands after a phone is linked by the server administrator."""
import re
from datetime import datetime, timezone
from decimal import Decimal
from app.models import db, Order, Customer, User, AuditLog
from app.services.order_service import cancel_order

ALLOWED_ROLES = {'SHOP_OWNER', 'SHOP_MANAGER'}


def handle_owner(shop, user, message):
    if not user or user.shop_id != shop.id or not user.active or user.role not in ALLOWED_ROLES:
        return 'Owner access denied.'
    body = (message.get('text') or {}).get('body', '').strip().upper() if message.get('type') == 'text' else ''
    if body in ('HELP', 'START', 'HI'):
        return 'Owner commands: PENDING, ORDER <id>, ACCEPT <id>, REJECT <id>, PREPARING <id>, READY <id>, DELIVERED <id>, SALES.'
    if body == 'PENDING':
        orders = Order.query.filter_by(shop_id=shop.id,status='Pending').order_by(Order.id).limit(20).all()
        return '\n'.join(f'#{o.id} AED {o.total:.2f}' for o in orders) or 'No pending orders.'
    if body == 'SALES':
        today = datetime.now(timezone.utc).date()
        orders = Order.query.filter(Order.shop_id==shop.id,Order.status!='Cancelled',Order.created_at>=today).all()
        return f'Today: {len(orders)} orders, AED {sum((o.total for o in orders),Decimal(0)):.2f} (includes unpaid orders).'
    match = re.fullmatch(r'(ORDER|ACCEPT|REJECT|PREPARING|READY|DELIVERED)\s+(\d+)', body)
    if not match:
        return 'Unknown command. Send HELP.'
    action, order_id = match.group(1), int(match.group(2))
    order = Order.query.filter_by(shop_id=shop.id,id=order_id).first()
    if not order:
        return 'Order not found.'
    if action == 'ORDER':
        return (f'#{order.id}: {order.status}, AED {order.total:.2f}, {order.payment_status}. '
                + ', '.join(f'{item.quantity} x {item.item_name}' for item in order.items))
    transitions = {
        'ACCEPT': ('Pending','Confirmed'), 'REJECT': ('Pending','Cancelled'),
        'PREPARING': ('Confirmed','Preparing'), 'READY': ('Preparing','Ready'),
        'DELIVERED': ('Ready','Delivered'),
    }
    source,target = transitions[action]
    if order.status != source:
        return f'Cannot {action.lower()} order #{order.id} from {order.status}.'
    if target == 'Cancelled':
        try: cancel_order(order)
        except ValueError as exc: return str(exc)
    else:
        order.status=target
    db.session.add(AuditLog(shop_id=shop.id,actor_id=user.id,action='whatsapp_order_status',details={'order_id':order.id,'from':source,'to':target}))
    return f'Order #{order.id}: {target}.'
