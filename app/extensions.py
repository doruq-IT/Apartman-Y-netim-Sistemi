from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_mail import Mail
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager
from flask_cors import CORS

limiter = Limiter(get_remote_address)

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()  # 💥 eksik olan buydu
bcrypt = Bcrypt()
jwt = JWTManager()
mail = Mail()
cors = CORS()


csrf = CSRFProtect()
