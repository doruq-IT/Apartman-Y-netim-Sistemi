from flask import Flask, send_from_directory
from flasgger import Swagger
from app.extensions import db, login_manager, migrate, csrf, bcrypt, jwt, cors
from app.routes import all_blueprints
from app.models import User
from app.routes.public import public_bp
from app.extensions import mail
from .context_processors import inject_counts
from app.routes.blog import blog_bp
from .routes.api import api_bp
from app.extensions import limiter
import os
import locale

def create_app():
    """Flask uygulama fabrikası (application factory)."""
    app = Flask(__name__)
    
    try:
        # Google App Engine gibi Linux tabanlı sistemler için
        locale.setlocale(locale.LC_TIME, 'tr_TR.UTF-8')
    except locale.Error:
        # Lokalde Windows'ta geliştirme yapıyorsanız diye yedek ayar
        try:
            locale.setlocale(locale.LC_TIME, 'Turkish_Turkey.1254')
        except locale.Error:
            # Hiçbiri olmazsa, uyarı ver ama uygulamayı durdurma
            app.logger.warning("Turkish locale could not be set. Date/time formats may appear in English.")

    app.config.from_object("config.Config")
    app.jinja_env.add_extension('jinja2.ext.do')
    
    Swagger(app)

    # Eklentileri (extensions) uygulamaya tanıt
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    jwt.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    limiter.init_app(app)
    bcrypt.init_app(app)
    mail.init_app(app)


    cors.init_app(
        app,
        resources={
            r"/api/*": {
                "origins": app.config.get("CORS_ORIGINS", "*"),
                "methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
                "allow_headers": ["Content-Type", "Authorization"],
                "expose_headers": ["Content-Type", "Authorization"],
                "supports_credentials": False,
            }
        }
    )

    # Blueprint'leri kaydet
    app.register_blueprint(public_bp)
    app.register_blueprint(api_bp, url_prefix='/api/v1')
    app.register_blueprint(blog_bp)

    @app.route("/favicon.ico")
    def favicon():
        return send_from_directory(
            os.path.join(app.root_path, "static"),
            "favicon.ico",
            mimetype="image/x-icon",
        )

    @app.route("/robots.txt")
    def robots():
        return send_from_directory(
            os.path.join(app.root_path, "static"),
            "robots.txt",
            mimetype="text/plain",
        )

    # Blueprint kaydedildikten SONRA onu CSRF korumasından muaf tutuyoruz.
    csrf.exempt(api_bp)

    @login_manager.user_loader
    def load_user(user_id):
        user = User.query.get(int(user_id))
        if user and user.is_active:
            return user
        return None

    app.context_processor(inject_counts)

    for bp in all_blueprints:
        app.register_blueprint(bp)

    return app
