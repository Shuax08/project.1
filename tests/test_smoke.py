import pytest
from app import create_app
from app.models import db
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
