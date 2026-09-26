from flask import jsonify

def install_error_handlers(app):
    @app.errorhandler(404)
    def not_found(e): return jsonify(error='not found'),404
    @app.errorhandler(500)
    def server_error(e):
        app.logger.exception(e); return jsonify(error='internal server error'),500
