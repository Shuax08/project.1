def build_receipt_data(order):
    from app.models import Shop,Customer,OrderItem
    shop=Shop.query.get(order.shop_id); customer=Customer.query.get(order.customer_id)
    return {'branding':'THALASSERI — Kerala Food • Fresh & Traditional','shop':shop.name,'contact':shop.phone,'order_number':order.id,'date':order.created_at.isoformat() if order.created_at else None,'customer':customer.name or customer.phone,'items':[{'name':x.item_name,'quantity':x.quantity,'unit_price':str(x.unit_price),'line_total':str(x.line_total)} for x in OrderItem.query.filter_by(order_id=order.id)],'subtotal':str(order.subtotal),'total':str(order.total),'payment_method':order.payment_method,'payment_status':order.payment_status,'order_status':order.status}
def render_receipt_text(data): return '\n'.join([data['branding'],data['shop'],f"Order #{data['order_number']}",*[f"{x['quantity']} x {x['name']}  {x['line_total']}" for x in data['items']],f"TOTAL {data['total']}",f"{data['payment_status']} / {data['order_status']}"])
def render_receipt_html(data):
    from flask import render_template
    return render_template('receipt.html',data=data)
