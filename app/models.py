from datetime import datetime, timezone
from decimal import Decimal
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

def utcnow(): return datetime.now(timezone.utc)

class Shop(db.Model):
    id=db.Column(db.Integer, primary_key=True); name=db.Column(db.String(160), nullable=False); slug=db.Column(db.String(80), unique=True, nullable=False, index=True); phone=db.Column(db.String(40)); address=db.Column(db.String(255)); latitude=db.Column(db.Numeric(10,7)); longitude=db.Column(db.Numeric(10,7)); safe_radius=db.Column(db.Numeric(10,2), default=500); status=db.Column(db.String(20), default='active', index=True); created_at=db.Column(db.DateTime(timezone=True), default=utcnow); updated_at=db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow)
class User(db.Model):
    id=db.Column(db.Integer, primary_key=True); shop_id=db.Column(db.Integer, db.ForeignKey('shop.id'), index=True); email=db.Column(db.String(160), unique=True, nullable=False); password_hash=db.Column(db.String(255), nullable=False); role=db.Column(db.String(30), nullable=False, default='SHOP_STAFF'); active=db.Column(db.Boolean, default=True); created_at=db.Column(db.DateTime(timezone=True), default=utcnow)
    def set_password(self,p): self.password_hash=generate_password_hash(p)
    def check_password(self,p): return check_password_hash(self.password_hash,p)
class Customer(db.Model):
    id=db.Column(db.Integer, primary_key=True); shop_id=db.Column(db.Integer, db.ForeignKey('shop.id'), nullable=False, index=True); name=db.Column(db.String(160)); phone=db.Column(db.String(40), nullable=False); address=db.Column(db.String(255)); latitude=db.Column(db.Numeric(10,7)); longitude=db.Column(db.Numeric(10,7)); created_at=db.Column(db.DateTime(timezone=True), default=utcnow); __table_args__=(db.UniqueConstraint('shop_id','phone'),)
class MenuItem(db.Model):
    id=db.Column(db.Integer, primary_key=True); shop_id=db.Column(db.Integer, db.ForeignKey('shop.id'), nullable=False, index=True); name=db.Column(db.String(160), nullable=False); description=db.Column(db.Text); category=db.Column(db.String(80)); price=db.Column(db.Numeric(12,2), nullable=False); image_url=db.Column(db.String(500)); available=db.Column(db.Boolean, default=True); sort_order=db.Column(db.Integer, default=0); created_at=db.Column(db.DateTime(timezone=True), default=utcnow); updated_at=db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow)
class Order(db.Model):
    id=db.Column(db.Integer, primary_key=True); shop_id=db.Column(db.Integer, db.ForeignKey('shop.id'), nullable=False, index=True); customer_id=db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False); status=db.Column(db.String(20), default='Pending', index=True); payment_status=db.Column(db.String(20), default='UNPAID'); payment_method=db.Column(db.String(30)); subtotal=db.Column(db.Numeric(12,2), nullable=False, default=0); total=db.Column(db.Numeric(12,2), nullable=False, default=0); idempotency_key=db.Column(db.String(120)); created_at=db.Column(db.DateTime(timezone=True), default=utcnow); __table_args__=(db.UniqueConstraint('shop_id','idempotency_key'),)
class OrderItem(db.Model):
    id=db.Column(db.Integer, primary_key=True); order_id=db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False, index=True); order=db.relationship('Order', backref='items'); menu_item_id=db.Column(db.Integer); item_name=db.Column(db.String(160), nullable=False); unit_price=db.Column(db.Numeric(12,2), nullable=False); quantity=db.Column(db.Integer, nullable=False); line_total=db.Column(db.Numeric(12,2), nullable=False)
class CreditAccount(db.Model):
    id=db.Column(db.Integer, primary_key=True); shop_id=db.Column(db.Integer, db.ForeignKey('shop.id'), nullable=False); customer_id=db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False, unique=True); credit_enabled=db.Column(db.Boolean, default=False); credit_limit=db.Column(db.Numeric(12,2), default=500); outstanding_balance=db.Column(db.Numeric(12,2), default=0)
class CreditTransaction(db.Model):
    id=db.Column(db.Integer, primary_key=True); account_id=db.Column(db.Integer, db.ForeignKey('credit_account.id'), nullable=False, index=True); kind=db.Column(db.String(30), nullable=False); amount=db.Column(db.Numeric(12,2), nullable=False); order_id=db.Column(db.Integer, db.ForeignKey('order.id')); note=db.Column(db.String(255)); created_at=db.Column(db.DateTime(timezone=True), default=utcnow)
class Payment(db.Model):
    id=db.Column(db.Integer, primary_key=True); shop_id=db.Column(db.Integer, db.ForeignKey('shop.id'), nullable=False, index=True); order_id=db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False); amount=db.Column(db.Numeric(12,2), nullable=False); status=db.Column(db.String(20), default='PENDING'); provider_ref=db.Column(db.String(160)); created_at=db.Column(db.DateTime(timezone=True), default=utcnow)
class PrinterSettings(db.Model):
    id=db.Column(db.Integer, primary_key=True); shop_id=db.Column(db.Integer, db.ForeignKey('shop.id'), unique=True, nullable=False); enabled=db.Column(db.Boolean, default=False); host=db.Column(db.String(255)); port=db.Column(db.Integer, default=9100)
class AuditLog(db.Model):
    id=db.Column(db.Integer, primary_key=True); shop_id=db.Column(db.Integer, db.ForeignKey('shop.id')); actor_id=db.Column(db.Integer, db.ForeignKey('user.id')); action=db.Column(db.String(120), nullable=False); details=db.Column(db.JSON); created_at=db.Column(db.DateTime(timezone=True), default=utcnow)
class Plan(db.Model):
    id=db.Column(db.Integer, primary_key=True); name=db.Column(db.String(80), unique=True); monthly_price=db.Column(db.Numeric(12,2), default=0)
class Subscription(db.Model):
    id=db.Column(db.Integer, primary_key=True); shop_id=db.Column(db.Integer, db.ForeignKey('shop.id'), unique=True); plan_id=db.Column(db.Integer, db.ForeignKey('plan.id')); status=db.Column(db.String(20), default='trial'); renews_at=db.Column(db.DateTime(timezone=True))
class BotSession(db.Model):
    id=db.Column(db.Integer, primary_key=True); shop_id=db.Column(db.Integer, db.ForeignKey('shop.id'), nullable=False); phone=db.Column(db.String(40), nullable=False); state=db.Column(db.String(40), default='start'); data=db.Column(db.JSON, default=dict); updated_at=db.Column(db.DateTime(timezone=True), default=utcnow); __table_args__=(db.UniqueConstraint('shop_id','phone'),)

class WhatsAppChannel(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    shop_id=db.Column(db.Integer, db.ForeignKey('shop.id'), nullable=False, unique=True, index=True)
    phone_number_id=db.Column(db.String(80), nullable=False, unique=True, index=True)
    display_number=db.Column(db.String(40), nullable=False)

class IncomingMessage(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    shop_id=db.Column(db.Integer, db.ForeignKey('shop.id'), nullable=False, index=True)
    message_id=db.Column(db.String(200), nullable=False, unique=True)
    recipient=db.Column(db.String(40), nullable=False)
    response=db.Column(db.Text)
    sent=db.Column(db.Boolean, nullable=False, default=False)
    order_id=db.Column(db.Integer, db.ForeignKey('order.id'))
    owner_notified=db.Column(db.Boolean, nullable=False, default=False)
    created_at=db.Column(db.DateTime(timezone=True), default=utcnow)

class OwnerWhatsAppIdentity(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    shop_id=db.Column(db.Integer, db.ForeignKey('shop.id'), nullable=False, index=True)
    user_id=db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    phone=db.Column(db.String(40), nullable=False)
    __table_args__=(db.UniqueConstraint('shop_id','phone'),db.UniqueConstraint('shop_id','user_id'))
