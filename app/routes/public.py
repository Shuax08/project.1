from flask import Blueprint, render_template, redirect, current_app, abort
from app.models import Shop
public=Blueprint('public',__name__)
@public.get('/s/<slug>')
def landing(slug):
    shop=Shop.query.filter_by(slug=slug,status='active').first_or_404(); return render_template('shop_landing.html',shop=shop)
@public.get('/s/<slug>/whatsapp')
def whatsapp(slug):
    shop=Shop.query.filter_by(slug=slug,status='active').first_or_404(); phone=''.join(c for c in (shop.phone or '') if c.isdigit())
    if not phone: abort(404)
    return redirect(f'https://wa.me/{phone}?text=START%20{shop.slug}')
