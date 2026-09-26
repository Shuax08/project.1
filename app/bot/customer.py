"""Deterministic WhatsApp ordering. Prices and availability always come from DB."""
import re
from decimal import Decimal
from app.models import (db, BotSession, Customer, MenuItem, Order, OrderItem,
                        CreditAccount, CreditTransaction, Shop)
from app.services.geo import safe_zone


def _cart_text(shop_id, cart):
    if not cart:
        return 'Your cart is empty. Send MENU to see food.'
    lines, total = [], Decimal('0')
    for key, quantity in cart.items():
        item = MenuItem.query.filter_by(id=int(key), shop_id=shop_id, available=True).first()
        if not item:
            continue
        amount = item.price * quantity
        total += amount
        lines.append(f'{item.id}. {item.name} x{quantity} — AED {amount:.2f}')
    return ('Cart:\n' + '\n'.join(lines) + f'\nTotal: AED {total:.2f}\n'
            'Send NAME your name, then share a WhatsApp location, then CONFIRM CASH. '
            'For enabled credit, send CONFIRM CREDIT.')


def handle_customer(shop, phone, message):
    """Process one verified message within the caller's database transaction."""
    session = BotSession.query.filter_by(shop_id=shop.id, phone=phone).first()
    if session is None:
        session = BotSession(shop_id=shop.id, phone=phone)
        db.session.add(session)
    customer = Customer.query.filter_by(shop_id=shop.id, phone=phone).first()
    if customer is None:
        customer = Customer(shop_id=shop.id, phone=phone)
        db.session.add(customer)
    db.session.flush()
    data = dict(session.data or {})
    cart = dict(data.get('cart') or {})
    body = (message.get('text') or {}).get('body', '').strip() if message.get('type') == 'text' else ''
    cmd = body.upper()
    if message.get('type') == 'location':
        loc = message.get('location') or {}
        try:
            lat, lon = float(loc['latitude']), float(loc['longitude'])
            check = safe_zone(shop, lat, lon)
        except (KeyError, TypeError, ValueError, OverflowError):
            return 'Invalid location. Share your current location again.'
        if not check['inside_safe_zone'] and shop.latitude is not None:
            return 'Sorry, this location is outside the delivery area.'
        customer.latitude, customer.longitude = lat, lon
        reply = 'Location saved. Send CONFIRM CASH to place your order.'
    elif cmd.startswith('START') or cmd in ('HI', 'HELLO', 'HELP'):
        reply = (f'Welcome to {shop.name}! Send MENU, ADD item-number quantity, '
                 'CART, NAME your-name, or STATUS.')
    elif cmd in ('MENU', 'CATEGORIES'):
        items = MenuItem.query.filter_by(shop_id=shop.id, available=True).order_by(MenuItem.sort_order, MenuItem.id).limit(40).all()
        reply = ('Menu:\n' + '\n'.join(f'{i.id}. {i.name} — AED {i.price:.2f}' for i in items)
                 + '\nSend ADD item-number quantity (example: ADD 1 2).') if items else 'The menu is empty right now.'
    elif cmd.startswith('NAME '):
        name = body[5:].strip()
        if not 1 <= len(name) <= 160:
            return 'Send NAME followed by your name (up to 160 characters).'
        customer.name = name
        reply = 'Name saved. Share your WhatsApp location, or send CART.'
    elif cmd.startswith('ADD '):
        match = re.fullmatch(r'ADD\s+(\d+)\s+(\d+)', cmd)
        if not match:
            return 'Use ADD item-number quantity, for example ADD 1 2.'
        item_id, quantity = map(int, match.groups())
        item = MenuItem.query.filter_by(shop_id=shop.id, id=item_id, available=True).first()
        if not item or quantity < 1 or quantity > 50:
            return 'Item unavailable or quantity invalid (1–50). Send MENU.'
        if str(item.id) not in cart and len(cart) >= 20:
            return 'Cart limit is 20 different items.'
        cart[str(item.id)] = min(50, cart.get(str(item.id), 0) + quantity)
        reply = f'Added {item.name}.\n' + _cart_text(shop.id, cart)
    elif cmd.startswith('REMOVE '):
        match = re.fullmatch(r'REMOVE\s+(\d+)', cmd)
        if not match:
            return 'Use REMOVE item-number.'
        cart.pop(str(int(match.group(1))), None)
        reply = _cart_text(shop.id, cart)
    elif cmd == 'CLEAR':
        cart = {}
        reply = 'Cart cleared. Send MENU to begin again.'
    elif cmd == 'CART':
        reply = _cart_text(shop.id, cart)
    elif cmd == 'STATUS':
        order = Order.query.filter_by(shop_id=shop.id, customer_id=customer.id).order_by(Order.id.desc()).first()
        reply = f'Order #{order.id}: {order.status} / {order.payment_status}' if order else 'No orders yet.'
    elif cmd.startswith('CONFIRM '):
        method = cmd[8:].strip()
        if method not in ('CASH', 'CREDIT') or not cart:
            return 'Add items first, then send CONFIRM CASH or CONFIRM CREDIT.'
        if not customer.name:
            return 'Send NAME your-name before confirming.'
        if shop.latitude is not None:
            if customer.latitude is None or customer.longitude is None:
                return 'Share your WhatsApp location before confirming.'
            if not safe_zone(shop, customer.latitude, customer.longitude)['inside_safe_zone']:
                return 'Your location is outside the delivery area.'
        items = []
        total = Decimal('0')
        for key, quantity in cart.items():
            item = MenuItem.query.filter_by(shop_id=shop.id, id=int(key), available=True).first()
            if not item or not 1 <= quantity <= 50:
                return 'Your cart contains an unavailable item. Please update it.'
            items.append((item, quantity))
            total += item.price * quantity
        account = None
        if method == 'CREDIT':
            account = CreditAccount.query.filter_by(shop_id=shop.id, customer_id=customer.id, credit_enabled=True).first()
            if not account or Decimal(account.outstanding_balance or 0) + total > account.credit_limit:
                return 'Credit is unavailable or the limit is exceeded. Send CONFIRM CASH.'
        order = Order(shop_id=shop.id, customer_id=customer.id, subtotal=total, total=total,
                      payment_method=method, payment_status='PAID' if method == 'CREDIT' else 'UNPAID')
        for item, quantity in items:
            order.items.append(OrderItem(menu_item_id=item.id, item_name=item.name,
                                         unit_price=item.price, quantity=quantity, line_total=item.price * quantity))
        db.session.add(order)
        db.session.flush()
        if account:
            account.outstanding_balance = Decimal(account.outstanding_balance or 0) + total
            db.session.add(CreditTransaction(account_id=account.id, kind='charge', amount=total, order_id=order.id))
        cart = {}
        reply = f'Order #{order.id} received! Total AED {total:.2f}. Payment: {method}. Send STATUS for updates.'
    else:
        reply = 'Send MENU, ADD item-number quantity, CART, REMOVE item-number, CLEAR, NAME your-name, STATUS or HELP.'
    data['cart'] = cart
    session.data = data
    return reply
