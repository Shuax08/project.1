import pytest
import json, hmac, hashlib
from app import create_app
from app.models import db, Shop, User, Customer, MenuItem, Order
@pytest.fixture
def app(tmp_path):
    class T: TESTING=True; SECRET_KEY='test'; SQLALCHEMY_DATABASE_URI='sqlite://'
    a=create_app(T)
    with a.app_context(): db.drop_all(); db.create_all()
    return a

def test_health(app):
    assert app.test_client().get('/health').status_code==200

def test_invalid_public_shop(app):
    assert app.test_client().get('/s/no-such-shop').status_code==404

def test_tenant_order_snapshot_and_csrf(app):
    with app.app_context():
        a,b=Shop(name='A',slug='a'),Shop(name='B',slug='b')
        db.session.add_all([a,b]); db.session.flush()
        owner=User(shop_id=a.id,email='a@example.test',role='SHOP_OWNER'); owner.set_password('password')
        customer_a=Customer(shop_id=a.id,phone='111'); customer_b=Customer(shop_id=b.id,phone='222')
        item_a=MenuItem(shop_id=a.id,name='Biryani',price='12.50'); item_b=MenuItem(shop_id=b.id,name='Other',price='1.00')
        db.session.add_all([owner,customer_a,customer_b,item_a,item_b]); db.session.commit()
        ids=(customer_a.id,customer_b.id,item_a.id,item_b.id)
    client=app.test_client()
    login=client.post('/api/auth/login',json={'email':'a@example.test','password':'password'})
    assert login.status_code==200
    headers={'X-CSRF-Token':login.json['csrf_token'],'Idempotency-Key':'order-1'}
    assert client.post('/api/orders',json={'customer_id':ids[0],'items':[{'item_id':ids[2],'quantity':2}]}).status_code==403
    assert client.post('/api/orders',headers=headers,json={'customer_id':ids[1],'items':[{'item_id':ids[2],'quantity':2}]}).status_code==404
    assert client.post('/api/orders',headers=headers,json={'customer_id':ids[0],'items':[{'item_id':ids[3],'quantity':2}]}).status_code==400
    response=client.post('/api/orders',headers=headers,json={'customer_id':ids[0],'items':[{'item_id':ids[2],'quantity':2,'price':'0.01'}]})
    assert response.status_code==201
    assert response.json['order']['total']=='25.00'
    assert response.json['order']['items'][0]['name']=='Biryani'
    assert client.post('/api/orders',headers=headers,json={'customer_id':ids[0],'items':[{'item_id':ids[2],'quantity':2}]}).json['duplicate']
    order_id=response.json['order']['id']
    assert client.patch(f'/api/orders/{order_id}',headers=headers,json={'payment_status':'PAID'}).status_code==400
    assert client.get(f'/api/customers/{ids[1]}').status_code==404
    assert client.post(f'/api/customers/{ids[1]}/credit',headers=headers,json={'kind':'enable'}).status_code==404
    assert client.post(f'/api/customers/{ids[0]}/credit',headers=headers,json={'kind':'enable','limit':'100'}).status_code==200
    assert client.post(f'/api/customers/{ids[0]}/credit',headers=headers,json={'kind':'charge','amount':'25','order_id':order_id}).json['balance']=='25.00'
    assert client.post(f'/api/customers/{ids[0]}/credit',headers=headers,json={'kind':'charge','amount':'25','order_id':order_id}).status_code==400
    assert client.post(f'/api/customers/{ids[0]}/credit',headers=headers,json={'kind':'repayment','amount':'10'}).json['balance']=='15.00'
    assert len(client.get(f'/api/customers/{ids[0]}/credit').json['transactions'])==2
    with app.app_context():
        assert Order.query.count()==1

def test_webhook_requires_real_verification(app):
    client=app.test_client()
    assert client.get('/webhooks/whatsapp?hub.verify_token=&hub.challenge=abc').status_code==403
    assert client.post('/webhooks/whatsapp',json={'shop_id':1,'from':'123'}).status_code==401

def test_whatsapp_customer_order_and_retry(app, monkeypatch):
    from app.models import WhatsAppChannel, IncomingMessage, CreditAccount
    from app.routes import webhooks as webhook_module
    app.config['WHATSAPP_APP_SECRET']='test-secret'
    app.config['WHATSAPP_VERIFY_TOKEN']='verify-secret'
    sent=[]
    monkeypatch.setattr(webhook_module,'send_text',lambda phone_id,to,body: sent.append((phone_id,to,body)))
    with app.app_context():
        a,b=Shop(name='One',slug='one'),Shop(name='Two',slug='two')
        db.session.add_all([a,b]);db.session.flush()
        db.session.add_all([WhatsAppChannel(shop_id=a.id,phone_number_id='111',display_number='971500000001'),WhatsAppChannel(shop_id=b.id,phone_number_id='222',display_number='971500000002'),MenuItem(shop_id=a.id,name='Biriyani',price='15.00'),MenuItem(shop_id=b.id,name='Other',price='0.01')]);db.session.commit()
        item=MenuItem.query.filter_by(shop_id=a.id).first().id
    client=app.test_client()
    assert client.get('/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=verify-secret&hub.challenge=abc').data==b'abc'
    counter=0
    def send(body,phone_id='111',sender='971511112222',kind='text'):
        nonlocal counter
        counter+=1
        payload={'object':'whatsapp_business_account','entry':[{'changes':[{'field':'messages','value':{'metadata':{'phone_number_id':phone_id},'messages':[{'id':f'wamid.{counter}','from':sender,'type':kind,kind:{'body':body} if kind=='text' else body}]}}]}]}
        raw=json.dumps(payload).encode()
        signature='sha256='+hmac.new(b'test-secret',raw,hashlib.sha256).hexdigest()
        return client.post('/webhooks/whatsapp',data=raw,headers={'X-Hub-Signature-256':signature,'Content-Type':'application/json'}),raw,signature
    assert send('MENU')[0].status_code==200
    assert 'Biriyani' in sent[-1][2] and 'Other' not in sent[-1][2]
    assert send(f'ADD {item} 2')[0].status_code==200
    assert send('NAME Test Customer')[0].status_code==200
    response,raw,signature=send('CONFIRM CASH')
    assert response.status_code==200 and 'AED 30.00' in sent[-1][2]
    assert client.post('/webhooks/whatsapp',data=raw,headers={'X-Hub-Signature-256':signature,'Content-Type':'application/json'}).status_code==200
    with app.app_context():
        assert Order.query.count()==1
        assert Order.query.first().total==30
        assert IncomingMessage.query.count()==4
    assert len(sent)==4
    assert send('MENU',phone_id='222')[0].status_code==200
    assert 'Biriyani' not in sent[-1][2]

def test_whatsapp_owner_tenant_permissions(app, monkeypatch):
    from app.models import WhatsAppChannel, OwnerWhatsAppIdentity, AuditLog
    from app.routes import webhooks as webhook_module
    app.config['WHATSAPP_APP_SECRET']='secret'
    sent=[]
    monkeypatch.setattr(webhook_module,'send_text',lambda channel,to,body: sent.append(body))
    with app.app_context():
        a,b=Shop(name='A',slug='owner-a'),Shop(name='B',slug='owner-b')
        db.session.add_all([a,b]);db.session.flush()
        owner=User(shop_id=a.id,email='owner@example.test',role='SHOP_OWNER',active=True)
        owner.set_password('password')
        ca,cb=Customer(shop_id=a.id,phone='101'),Customer(shop_id=b.id,phone='202')
        db.session.add_all([owner,ca,cb]);db.session.flush()
        order_a,order_b=Order(shop_id=a.id,customer_id=ca.id,total=10,subtotal=10),Order(shop_id=b.id,customer_id=cb.id,total=99,subtotal=99)
        db.session.add_all([order_a,order_b,WhatsAppChannel(shop_id=a.id,phone_number_id='123',display_number='971500000000'),OwnerWhatsAppIdentity(shop_id=a.id,user_id=owner.id,phone='971511110000')]);db.session.commit()
        own_id,other_id=order_a.id,order_b.id
    sequence=0
    def send(command,number):
        nonlocal sequence
        sequence+=1
        payload={'object':'whatsapp_business_account','entry':[{'changes':[{'field':'messages','value':{'metadata':{'phone_number_id':'123'},'messages':[{'id':f'wamid.{sequence}','from':number,'type':'text','text':{'body':command}}]}}]}]}
        raw=json.dumps(payload).encode()
        signature='sha256='+hmac.new(b'secret',raw,hashlib.sha256).hexdigest()
        return app.test_client().post('/webhooks/whatsapp',data=raw,headers={'X-Hub-Signature-256':signature,'Content-Type':'application/json'})
    assert send(f'ACCEPT {other_id}','971511110000').status_code==200
    assert sent[-1]=='Order not found.'
    assert send(f'ACCEPT {own_id}','971511110000').status_code==200
    assert sent[-1]==f'Order #{own_id}: Confirmed.'
    assert send(f'ACCEPT {own_id}','971511110000').status_code==200
    assert 'Cannot accept' in sent[-1]
    with app.app_context():
        assert db.session.get(Order,other_id).status=='Pending'
        assert AuditLog.query.count()==1

def test_new_order_notifies_linked_owner_once(app, monkeypatch):
    from app.models import WhatsAppChannel, OwnerWhatsAppIdentity
    from app.routes import webhooks as webhook_module
    app.config['WHATSAPP_APP_SECRET']='secret'
    sent=[]
    monkeypatch.setattr(webhook_module,'send_text',lambda channel,to,body: sent.append((to,body)))
    with app.app_context():
        shop=Shop(name='Shop',slug='notify');db.session.add(shop);db.session.flush()
        owner=User(shop_id=shop.id,email='notify@example.test',role='SHOP_OWNER',active=True)
        owner.set_password('test')
        db.session.add(owner);db.session.flush()
        item=MenuItem(shop_id=shop.id,name='Tea',price=2)
        db.session.add_all([item,WhatsAppChannel(shop_id=shop.id,phone_number_id='321',display_number='971500000003'),OwnerWhatsAppIdentity(shop_id=shop.id,user_id=owner.id,phone='971599990000')]);db.session.commit()
        item_id=item.id
    def send(command,index):
        payload={'object':'whatsapp_business_account','entry':[{'changes':[{'field':'messages','value':{'metadata':{'phone_number_id':'321'},'messages':[{'id':f'wamid.{index}','from':'971511112222','type':'text','text':{'body':command}}]}}]}]}
        raw=json.dumps(payload).encode()
        signature='sha256='+hmac.new(b'secret',raw,hashlib.sha256).hexdigest()
        return app.test_client().post('/webhooks/whatsapp',data=raw,headers={'X-Hub-Signature-256':signature,'Content-Type':'application/json'})
    assert send(f'ADD {item_id} 1',1).status_code==200
    assert send('NAME Tester',2).status_code==200
    assert send('CONFIRM CASH',3).status_code==200
    assert send('CONFIRM CASH',3).status_code==200
    assert len([message for to,message in sent if to=='971599990000'])==1
    with app.app_context(): assert Order.query.count()==1

def test_cancel_credit_order_reverses_ledger(app):
    from app.models import CreditAccount, CreditTransaction
    from app.services.order_service import cancel_order
    with app.app_context():
        shop=Shop(name='Shop',slug='credit-reversal');db.session.add(shop);db.session.flush()
        customer=Customer(shop_id=shop.id,phone='123');db.session.add(customer);db.session.flush()
        account=CreditAccount(shop_id=shop.id,customer_id=customer.id,credit_enabled=True,credit_limit=100,outstanding_balance=25)
        order=Order(shop_id=shop.id,customer_id=customer.id,total=25,subtotal=25,payment_status='PAID',payment_method='CREDIT')
        db.session.add_all([account,order]);db.session.flush()
        db.session.add(CreditTransaction(account_id=account.id,kind='charge',amount=25,order_id=order.id))
        cancel_order(order);db.session.commit()
        assert order.status=='Cancelled' and order.payment_status=='REFUNDED'
        assert account.outstanding_balance==0
        assert [x.kind for x in CreditTransaction.query.filter_by(account_id=account.id).order_by(CreditTransaction.id)]==['charge','reversal']
