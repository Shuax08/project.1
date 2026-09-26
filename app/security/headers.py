def install_security_headers(app):
    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options']='nosniff'; response.headers['X-Frame-Options']='DENY'; response.headers['Referrer-Policy']='strict-origin-when-cross-origin'; response.headers['Permissions-Policy']='geolocation=(self)'; response.headers['Content-Security-Policy']="default-src 'self'; style-src 'self' 'unsafe-inline'"
        if app.config.get('SESSION_COOKIE_SECURE'): response.headers['Strict-Transport-Security']='max-age=31536000; includeSubDomains'
        return response
