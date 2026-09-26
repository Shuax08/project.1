from math import radians,sin,cos,asin,sqrt
def distance_meters(lat1,lon1,lat2,lon2):
    p=radians(float(lat1)); q=radians(float(lat2)); dp=radians(float(lat2)-float(lat1)); dl=radians(float(lon2)-float(lon1)); a=sin(dp/2)**2+cos(p)*cos(q)*sin(dl/2)**2; return 6371000*2*asin(sqrt(a))
def safe_zone(shop,lat,lon):
    if not (-90<=float(lat)<=90 and -180<=float(lon)<=180) or shop.latitude is None or shop.longitude is None:return {'inside_safe_zone':False,'distance':None,'allowed_radius':str(shop.safe_radius)}
    d=distance_meters(shop.latitude,shop.longitude,lat,lon); return {'inside_safe_zone':d<=float(shop.safe_radius or 0),'distance':round(d,2),'allowed_radius':str(shop.safe_radius)}
