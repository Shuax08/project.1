from functools import wraps
from flask import session, jsonify
from app.models import User, db

def login_required(fn):
    @wraps(fn)
    def wrapper(*a,**kw):
        user=db.session.get(User,session.get('user_id')) if session.get('user_id') else None
        if not user or not user.active: return jsonify(error='authentication required'),401
        return fn(user,*a,**kw)
    return wrapper

def roles(*allowed):
    def deco(fn):
        @wraps(fn)
        def wrapper(user,*a,**kw):
            if user.role not in allowed: return jsonify(error='forbidden'),403
            return fn(user,*a,**kw)
        return wrapper
    return deco
