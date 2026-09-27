"""Shared order transition logic used by API and WhatsApp handlers."""
from decimal import Decimal
from app.models import db, CreditAccount, CreditTransaction


def cancel_order(order):
    if order.status in ('Delivered', 'Cancelled'):
        raise ValueError('order cannot be cancelled')
    if order.payment_method == 'CREDIT' and order.payment_status == 'PAID':
        account = CreditAccount.query.filter_by(shop_id=order.shop_id,customer_id=order.customer_id).first()
        if account is None or Decimal(account.outstanding_balance or 0) < order.total:
            raise ValueError('credit account requires manual reconciliation')
        account.outstanding_balance = Decimal(account.outstanding_balance) - order.total
        db.session.add(CreditTransaction(account_id=account.id,kind='reversal',amount=order.total,order_id=order.id))
        order.payment_status = 'REFUNDED'
    order.status = 'Cancelled'
