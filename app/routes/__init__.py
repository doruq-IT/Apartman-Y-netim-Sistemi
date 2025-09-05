from .auth import auth_bp
from .resident import resident_bp
from .admin import admin_bp
from .superadmin import superadmin_bp
from .document import document_bp
from .announcement import announcement_bp
from .request_routes import request_bp
from .expense_routes import expense_bp # YENİ: Yeni blueprint'i import ediyoruz
from .poll_routes import poll_bp

all_blueprints = [
    auth_bp,
    resident_bp,
    admin_bp,
    superadmin_bp,
    document_bp,
    announcement_bp,
    request_bp,
    expense_bp,
    poll_bp
]