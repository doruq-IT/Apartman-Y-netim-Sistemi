from flask import current_app
from itsdangerous.url_safe import URLSafeTimedSerializer as Serializer
from app.extensions import db
from flask_login import UserMixin
from datetime import datetime
from sqlalchemy import UniqueConstraint, Table, Column, Integer, ForeignKey
import enum


# YENİ: Apartmanları temsil eden model
class Apartment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), unique=True, nullable=False)
    address = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Apartment {self.name}>'


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # YENİ: Her kullanıcı artık bir apartmana ait olacak
    apartment_id = db.Column(db.Integer, db.ForeignKey('apartment.id'), nullable=False)
    
    block_id = db.Column(db.Integer, db.ForeignKey('block.id'), nullable=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(20), default="resident")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    phone_number = db.Column(db.String(20), nullable=True)
    daire_no = db.Column(db.String(20), nullable=True) # Daire Numarası (Örn: "5", "10A")
    
    is_email_verified = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=False, nullable=False)
    
    # YENİ: User ve Apartment arasındaki ilişki
    apartment = db.relationship('Apartment', backref=db.backref('users', lazy='dynamic'))
    block = db.relationship('Block', backref=db.backref('users', lazy='dynamic'))
    def get_reset_token(self, expires_sec=1800):
        """
        Güvenli ve süresi (varsayılan 30 dakika) olan bir şifre sıfırlama anahtarı (token) oluşturur.
        """
        s = Serializer(current_app.config['SECRET_KEY'])
        return s.dumps({'user_id': self.id})

    @staticmethod
    def verify_reset_token(token, expires_sec=1800):
        """
        Gönderilen anahtarın geçerli olup olmadığını kontrol eder.
        Eğer anahtar geçerliyse ilgili kullanıcıyı, değilse None döndürür.
        """
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            user_id = s.loads(
                token,
                max_age=expires_sec
            )['user_id']
        except:
            return None
        return User.query.get(user_id)
    
        # ─── E-POSTA DOĞRULAMA TOKEN'ı ──────────────────────────────────
    def generate_confirmation_token(self):
        """Kullanıcı ID’sini imzalı token’a çevirir."""
        s = Serializer(current_app.config["SECRET_KEY"])
        return s.dumps({"confirm": self.id})

    @staticmethod
    def verify_confirmation_token(token, expires_sec=86400):
        """Token geçerliyse User nesnesini döndürür, aksi hâlde None."""
        s = Serializer(current_app.config["SECRET_KEY"])
        try:
            user_id = s.loads(token, max_age=expires_sec)["confirm"]
        except Exception:
            return None
        return User.query.get(user_id)
    
    def get_delete_token(self, expires_sec=1800):
        """
        Hesap silme onayı için güvenli ve süreli (30 dk) bir token oluşturur.
        """
        s = Serializer(current_app.config['SECRET_KEY'])
        # Farklı bir payload anahtarı ('delete_user_id') kullanıyoruz.
        return s.dumps({'delete_user_id': self.id})

    @staticmethod
    def verify_delete_token(token, expires_sec=1800):
        """
        Gönderilen hesap silme token'ının geçerli olup olmadığını kontrol eder.
        Geçerliyse kullanıcıyı, değilse None döndürür.
        """
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            user_id = s.loads(
                token,
                max_age=expires_sec
            )['delete_user_id'] # Sadece 'delete_user_id' anahtarını kabul eder.
        except:
            return None
        return User.query.get(user_id)



class Dues(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # YENİ: Her aidat bir apartmana ait
    apartment_id = db.Column(db.Integer, db.ForeignKey('apartment.id'), nullable=False)
    
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    is_paid = db.Column(db.Boolean, default=False)
    description = db.Column(db.String(255))
    receipt_filename = db.Column(db.String(255))
    payment_date = db.Column(db.DateTime)
    receipt_upload_date = db.Column(db.DateTime, nullable=True)
    
    user = db.relationship("User", backref=db.backref("dues", lazy=True))
    apartment = db.relationship('Apartment', backref=db.backref('dues', lazy=True))


class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # YENİ: Her döküman bir apartmana ait
    apartment_id = db.Column(db.Integer, db.ForeignKey('apartment.id'), nullable=False)
    
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    doc_type = db.Column(db.String(100))
    
    user = db.relationship('User', backref='documents')
    apartment = db.relationship('Apartment', backref=db.backref('documents', lazy=True))

announcement_read_status = Table('announcement_read_status',
    db.Model.metadata,
    Column('user_id', Integer, ForeignKey('user.id'), primary_key=True),
    Column('announcement_id', Integer, ForeignKey('announcement.id'), primary_key=True)
)
    
class Announcement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # YENİ: Her duyuru bir apartmana ait
    apartment_id = db.Column(db.Integer, db.ForeignKey('apartment.id'), nullable=False)
    
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    creator = db.relationship('User', backref='announcements')
    apartment = db.relationship('Apartment', backref=db.backref('announcements', lazy=True))

    read_by_users = db.relationship('User', secondary=announcement_read_status,
                                    backref=db.backref('read_announcements', lazy='dynamic'))

class RequestStatus(enum.Enum):
    BEKLEMEDE = "Beklemede"
    ISLEMDE = "İşlemde"
    TAMAMLANDI = "Tamamlandı"


class Request(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    apartment_id = db.Column(db.Integer, db.ForeignKey('apartment.id'), nullable=False)

    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.Enum(RequestStatus), nullable=False, default=RequestStatus.BEKLEMEDE)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reply = db.Column(db.Text, nullable=True)

    # Talep sahibi (örn. bir resident)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('requests', lazy=True))

    # Yanıtlayan / işlemi yapan admin
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_by = db.relationship('User', foreign_keys=[created_by_id], backref='created_requests')

    apartment = db.relationship('Apartment', backref=db.backref('requests', lazy=True))
    
    # ---- Arıza & Bakım için yeni alanlar ----
    category = db.Column(db.String(50), nullable=False, default="Yeni talep")   # Arıza, Bakım, Yeni talep, Diğer
    priority = db.Column(db.String(10), nullable=False, default="Orta")         # Düşük, Orta, Yüksek
    location = db.Column(db.String(100), nullable=True)                         # Asansör, Elektrik, ...; Diğer serbest metin
    attachment_url = db.Column(db.Text, nullable=True)                          # Yüklenen foto/pdf GCS URL'i
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    # -----------------------------------------
    
class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # YENİ: Her masraf bir apartmana ait
    apartment_id = db.Column(db.Integer, db.ForeignKey('apartment.id'), nullable=False)
    
    description = db.Column(db.Text, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    expense_date = db.Column(db.Date, nullable=False)
    invoice_filename = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    creator = db.relationship('User', backref='expenses')
    apartment = db.relationship('Apartment', backref=db.backref('expenses', lazy=True))


class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # YENİ: Her işlem bir apartmana ait
    apartment_id = db.Column(db.Integer, db.ForeignKey('apartment.id'), nullable=False)
    
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(255), nullable=False)
    transaction_date = db.Column(db.DateTime, default=datetime.utcnow)
    source_type = db.Column(db.String(50))
    source_id = db.Column(db.Integer)
    # YENİ: İşlemin hangi kullanıcıyla ilgili olduğunu belirtmek için (opsiyonel ama faydalı)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    user = db.relationship('User', backref='transactions')
    apartment = db.relationship('Apartment', backref=db.backref('transactions', lazy=True))
    

class Poll(db.Model):
    """Anketleri temsil eden model."""
    __tablename__ = 'poll'
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expiration_date = db.Column(db.DateTime, nullable=True)
    
    # <-- YENİ EKLENEN SATIR
    # Bu anketin sonuç bildiriminin gönderilip gönderilmediğini takip eder.
    result_notification_sent = db.Column(db.Boolean, default=False, nullable=False)
    # --- EKLEME SONU ---
    
    # İlişkiler
    apartment_id = db.Column(db.Integer, db.ForeignKey('apartment.id'), nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    creator = db.relationship('User', backref='polls_created')
    options = db.relationship('PollOption', backref='poll', lazy='dynamic', cascade="all, delete-orphan")
    votes = db.relationship('Vote', backref='poll', lazy='dynamic', cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Poll "{self.question[:30]}...">'



class PollOption(db.Model):
    """Bir ankete ait seçenekleri temsil eden model."""
    __tablename__ = 'poll_option'
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(200), nullable=False)
    
    # İlişkiler
    poll_id = db.Column(db.Integer, db.ForeignKey('poll.id'), nullable=False)
    
    votes = db.relationship('Vote', backref='option', lazy='dynamic', cascade="all, delete-orphan")

    def __repr__(self):
        return f'<PollOption {self.text}>'


class Vote(db.Model):
    """Kullanıcıların anketlere verdiği oyları temsil eden model."""
    __tablename__ = 'vote'
    id = db.Column(db.Integer, primary_key=True)
    voted_at = db.Column(db.DateTime, default=datetime.utcnow)

    # İlişkiler
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    poll_id = db.Column(db.Integer, db.ForeignKey('poll.id'), nullable=False)
    option_id = db.Column(db.Integer, db.ForeignKey('poll_option.id'), nullable=False)

    user = db.relationship('User', backref='votes')

    # Bir kullanıcının aynı ankete sadece bir kez oy verebilmesini sağlayan kısıtlama
    __table_args__ = (UniqueConstraint('user_id', 'poll_id', name='_user_poll_uc'),)

    def __repr__(self):
        return f'<Vote by User {self.user_id} for Poll {self.poll_id}>'


# === YENİ EKLENECEK USTA MODELİ ===

class Craftsman(db.Model):
    """
    Yöneticiler tarafından eklenen ve sakinler tarafından görüntülenebilen
    anlaşmalı ustaları (elektrikçi, su tesisatçısı vb.) temsil eden model.
    """
    __tablename__ = 'craftsman'
    id = db.Column(db.Integer, primary_key=True)
    
    # Her usta, bir apartmana aittir.
    apartment_id = db.Column(db.Integer, db.ForeignKey('apartment.id'), nullable=False)
    
    specialty = db.Column(db.String(100), nullable=False)  # Uzmanlık alanı (örn: Elektrik)
    full_name = db.Column(db.String(150), nullable=False) # Adı Soyadı
    phone_number = db.Column(db.String(20), nullable=False)  # Telefon numarası
    notes = db.Column(db.Text, nullable=True) # Yönetici için ek notlar (isteğe bağlı)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # İlişki
    apartment = db.relationship('Apartment', backref=db.backref('craftsmen', lazy=True))

    def __repr__(self):
        return f'<Craftsman {self.full_name} ({self.specialty})>'

class CommonArea(db.Model):
    """
    Yöneticiler tarafından tanımlanabilen, rezerve edilebilir ortak alanları
    (Spor Salonu, Toplantı Odası vb.) temsil eden model.
    """
    __tablename__ = 'common_area'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    # Bu alanın rezervasyona açık olup olmadığını belirtir (örn: bakımda).
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    capacity = db.Column(db.Integer, nullable=False, default=1)    
    # Her ortak alan, bir apartmana aittir.
    apartment_id = db.Column(db.Integer, db.ForeignKey('apartment.id'), nullable=False)
    
    # İlişkiler
    apartment = db.relationship('Apartment', backref=db.backref('common_areas', lazy=True))
    reservations = db.relationship('Reservation', backref='common_area', lazy='dynamic', cascade="all, delete-orphan")

    def __repr__(self):
        return f'<CommonArea {self.name}>'


class Reservation(db.Model):
    """
    Sakinlerin ortak alanlar için yaptığı rezervasyon kayıtlarını tutan model.
    """
    __tablename__ = 'reservation'
    id = db.Column(db.Integer, primary_key=True)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    notes = db.Column(db.Text, nullable=True) # Sakinin rezervasyon notu
    num_of_people = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Rezervasyonu yapan kullanıcı (sakin)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    # Rezerve edilen ortak alan
    common_area_id = db.Column(db.Integer, db.ForeignKey('common_area.id'), nullable=False)
    # Rezervasyonun ait olduğu apartman (sorguları kolaylaştırmak için)
    apartment_id = db.Column(db.Integer, db.ForeignKey('apartment.id'), nullable=False)
    
    # İlişkiler
    user = db.relationship('User', backref=db.backref('reservations', lazy=True))
    apartment = db.relationship('Apartment', backref=db.backref('reservations', lazy=True))

    def __repr__(self):
        return f'<Reservation for {self.common_area.name} by User {self.user_id}>'

class Block(db.Model):
    """
    Bir apartmana (siteye) ait olan binaları (blokları) temsil eder.
    Örn: Blue Life-1 sitesine ait G-1 Blok.
    """
    __tablename__ = 'block'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # Örn: "G-1 Blok", "A Blok"
    
    # Her blok, bir apartmana/siteye aittir. Bu en önemli bağlantıdır.
    apartment_id = db.Column(db.Integer, db.ForeignKey('apartment.id'), nullable=False)
    
    # İlişki: Bu sayede bir apartmanın tüm bloklarına kolayca erişebiliriz.
    apartment = db.relationship('Apartment', backref=db.backref('blocks', lazy='dynamic', cascade="all, delete-orphan"))

    def __repr__(self):
        return f'<Block {self.name}>'

# ===== YENİ EKLENECEK BLOG YAZISI MODELİ =====
class Post(db.Model):
    __tablename__ = 'post'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    # SEO dostu URL'ler için (örn: /blog/apartman-yonetimi-ipuclari)
    slug = db.Column(db.String(255), unique=True, nullable=False)
    image_url = db.Column(db.String(512), nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Yöneticinin yazıyı taslak olarak kaydetmesine olanak tanır
    is_published = db.Column(db.Boolean, default=False, nullable=False)

    # Yazının hangi apartmana ait olduğu
    apartment_id = db.Column(db.Integer, db.ForeignKey('apartment.id'), nullable=False)
    
    # Yazıyı yazan kullanıcı (yönetici)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # İlişkiler
    author = db.relationship('User', backref=db.backref('posts', lazy=True))
    apartment = db.relationship('Apartment', backref=db.backref('posts', lazy=True))

    def __repr__(self):
        return f'<Post "{self.title}">'
# ===== YENİ MODEL BİTİŞİ =====


# ===== Otomatik gider yaratma =====
class RecurringExpense(db.Model):
    """
    Yöneticiler tarafından tanımlanan ve her ay otomatik olarak 
    aidat oluşturulmasını sağlayan kuralları temsil eder.
    """
    __tablename__ = 'recurring_expense'
    id = db.Column(db.Integer, primary_key=True)
    
    # Bu kuralın hangi apartmana ait olduğu
    apartment_id = db.Column(db.Integer, db.ForeignKey('apartment.id'), nullable=False)
    
    # Kuralın açıklaması (örn: "Aylık Aidat", "Personel Maaşı")
    description = db.Column(db.String(200), nullable=False)
    
    # Her ay oluşturulacak aidatın tutarı
    amount = db.Column(db.Float, nullable=False)
    
    # Ayın hangi gününde aidatın oluşturulacağı (1-28 arası bir sayı)
    # 29, 30, 31 gibi günler her ayda olmadığı için problem yaratabilir. 
    # Bu yüzden genellikle 28 ile sınırlandırmak en güvenlisidir.
    day_of_month = db.Column(db.Integer, nullable=False)
    
    # Bu kuralın aktif olup olmadığını belirtir. Yönetici istediğinde durdurabilir.
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    apartment = db.relationship('Apartment', backref=db.backref('recurring_expenses', lazy=True))

    def __repr__(self):
        return f'<RecurringExpense {self.description} - Ayın {self.day_of_month}. günü>'

# app/models.py dosyasının sonuna bu sınıfı ekleyin

class DynamicContent(db.Model):
    """
    Yöneticiler tarafından güncellenebilen metin içeriklerini (kurallar,
    gizlilik politikası vb.) saklamak için kullanılan model.
    """
    __tablename__ = 'dynamic_content'
    id = db.Column(db.Integer, primary_key=True)
    
    # İçeriği programatik olarak bulmak için kullanılacak benzersiz anahtar
    # Örn: "site_rules", "pool_rules"
    key = db.Column(db.String(50), unique=True, nullable=False, index=True)
    
    # İçeriğin başlığı (örn: "Site ve Apartman Genel Kuralları")
    title = db.Column(db.String(200), nullable=False)
    
    # İçeriğin kendisi (HTML formatında saklanacak)
    content = db.Column(db.Text, nullable=False)
    
    # Son güncellenme tarihini otomatik olarak kaydeder
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<DynamicContent {self.key}>'

# app/models.py dosyasının sonlarına doğru eklenecek

class CraftsmanRequestLog(db.Model):
    """
    Bir sakinin bir usta için iletişim bilgisi talebini loglayan model.
    """
    __tablename__ = 'craftsman_request_log'
    id = db.Column(db.Integer, primary_key=True)
    
    # Talebi yapan sakin
    resident_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    # Talep edilen usta
    craftsman_id = db.Column(db.Integer, db.ForeignKey('craftsman.id'), nullable=False)
    # Talebin yapıldığı apartman
    apartment_id = db.Column(db.Integer, db.ForeignKey('apartment.id'), nullable=False)
    
    # Talebin ne zaman yapıldığı
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # İlişkiler (raporlama için faydalı)
    resident = db.relationship('User', backref='craftsman_requests')
    craftsman = db.relationship('Craftsman', backref='requests')

    def __repr__(self):
        return f'<CraftsmanRequestLog from User {self.resident_id} for Craftsman {self.craftsman_id}>'

# YENİ: Hem FCM hem de HMS token'larını saklamak için yeni model
class PushToken(db.Model):
    __tablename__ = 'push_token'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    token = db.Column(db.String(512), nullable=False, index=True)
    
    # Token'ın hangi servise ait olduğunu belirtir: 'fcm' (Google) veya 'hms' (Huawei)
    service = db.Column(db.String(10), nullable=False, default='fcm') 
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('push_tokens', lazy='dynamic', cascade="all, delete-orphan"))

    def __repr__(self):
        return f'<PushToken for User {self.user_id} ({self.service})>'
