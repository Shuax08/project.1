from flask import Flask, jsonify, request, session
import hmac
import os
import click
from flask_cors import CORS
from flask_migrate import Migrate
from dotenv import load_dotenv
from .config import Config
from .models import db
from .routes.api import api
from .routes.public import public
from .routes.webhooks import webhooks
from .security.headers import install_security_headers
from .security.error_handler import install_error_handlers

migrate = Migrate()

def create_app(config_object=None):
    load_dotenv()
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_object or Config)
    if not app.config.get('TESTING') and os.getenv('FLASK_ENV') == 'production':
        if app.config['SECRET_KEY'] == 'dev-only-change-me' or not app.config['SESSION_COOKIE_SECURE']:
            raise RuntimeError('Production requires SECRET_KEY and SESSION_COOKIE_SECURE=true')
        if not app.config['SQLALCHEMY_DATABASE_URI'].startswith(('postgresql://','postgresql+')):
            raise RuntimeError('Production requires PostgreSQL DATABASE_URL')
    db.init_app(app)
    migrate.init_app(app, db)
    # Cookie authenticated APIs must not accept credentialed cross-origin requests.
    CORS(app, resources={r'/health': {'origins': '*'}})
    app.register_blueprint(api, url_prefix='/api')
    app.register_blueprint(public)
    app.register_blueprint(webhooks, url_prefix='/webhooks')
    @app.before_request
    def check_csrf():
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE') and request.endpoint not in ('api.login', 'webhooks.receive') and session.get('user_id'):
            expected = session.get('csrf_token', '')
            if not expected or not hmac.compare_digest(expected, request.headers.get('X-CSRF-Token', '')):
                return jsonify(error='invalid CSRF token'), 403
    install_security_headers(app)
    install_error_handlers(app)
    @app.cli.command('init-db')
    def init_db():
        db.create_all()
        print('Database initialized')
    @app.cli.command('bootstrap')
    @click.option('--slug',required=True)
    @click.option('--name',required=True)
    @click.option('--email',required=True)
    @click.password_option()
    def bootstrap(slug,name,email,password):
        from .models import Shop, User
        if Shop.query.filter_by(slug=slug).first() or User.query.filter_by(email=email).first():
            raise click.ClickException('Shop slug or email already exists')
        shop=Shop(slug=slug,name=name)
        db.session.add(shop); db.session.flush()
        owner=User(shop_id=shop.id,email=email,role='SHOP_OWNER')
        owner.set_password(password)
        db.session.add(owner); db.session.commit()
        click.echo(f'Created shop {slug} and owner {email}')
    @app.cli.command('configure-whatsapp')
    @click.option('--slug',required=True)
    @click.option('--phone-number-id',required=True)
    @click.option('--display-number',required=True)
    def configure_whatsapp(slug,phone_number_id,display_number):
        from .models import Shop, WhatsAppChannel
        shop=Shop.query.filter_by(slug=slug).first()
        if not shop: raise click.ClickException('Shop not found')
        duplicate=WhatsAppChannel.query.filter_by(phone_number_id=phone_number_id).first()
        if duplicate and duplicate.shop_id!=shop.id: raise click.ClickException('Phone number ID already belongs to another shop')
        channel=WhatsAppChannel.query.filter_by(shop_id=shop.id).first()
        if not channel: channel=WhatsAppChannel(shop_id=shop.id)
        channel.phone_number_id=phone_number_id
        channel.display_number=display_number
        shop.phone=display_number
        db.session.add(channel); db.session.commit()
        click.echo(f'WhatsApp configured for {slug}')
    @app.cli.command('add-menu-item')
    @click.option('--slug',required=True)
    @click.option('--name',required=True)
    @click.option('--price',required=True)
    def add_menu_item(slug,name,price):
        from decimal import Decimal, InvalidOperation
        from .models import Shop, MenuItem
        shop=Shop.query.filter_by(slug=slug).first()
        if not shop: raise click.ClickException('Shop not found')
        try: amount=Decimal(price).quantize(Decimal('0.01'))
        except InvalidOperation: raise click.ClickException('Invalid price')
        if not amount.is_finite() or amount<0: raise click.ClickException('Invalid price')
        item=MenuItem(shop_id=shop.id,name=name,price=amount)
        db.session.add(item); db.session.commit()
        click.echo(f'Added item #{item.id}: {name} AED {amount:.2f}')
    @app.get('/health')
    def health():
        return jsonify({'status': 'ok', 'service': 'thalasseri'})
    return app
