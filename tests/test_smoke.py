import pytest
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
