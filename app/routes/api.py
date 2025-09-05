from flask import Blueprint, request, jsonify, url_for, send_from_directory, current_app, redirect
from datetime import datetime
import uuid
import os
import re
from datetime import timezone
from app.gcs_utils import upload_to_gcs 
from app.models import User, Announcement, Dues, Request as RequestModel, Document, Poll, Vote, PollOption, Craftsman, Block, Apartment, RequestStatus, Transaction, Expense, PushToken
from dateutil.relativedelta import relativedelta
from app.extensions import db
from app.email import send_email
from werkzeug.datastructures import FileStorage
from app.forms.auth_forms import RegisterForm
from app.forms.auth_forms import ResetPasswordForm
from app.models import CraftsmanRequestLog
from sqlalchemy import func
from werkzeug.datastructures import MultiDict
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from app.models import Apartment, Block
from app.models import DynamicContent
from bs4 import BeautifulSoup


# API için yeni bir Blueprint oluşturuyoruz.
api_bp = Blueprint("api", __name__)


# === GÜNCELLENMİŞ YARDIMCI FONKSİYONLAR ===
def api_success(data, msg="İşlem başarılı.", status_code=200):
    """Standart bir başarılı API cevabı oluşturur."""
    return jsonify({
        "success": True,
        "msg": msg, # <-- YENİ EKLENDİ
        "error": None,
        "errorMessage": "",
        "data": data
    }), status_code

def api_error(message, status_code):
    """Standart bir hatalı API cevabı oluşturur."""
    return jsonify({
        "success": False,
        "msg": "", # <-- YENİ EKLENDİ
        "error": True,
        "errorMessage": message,
        "data": None
    }), status_code
# =================================

def format_tl(value):
    # 7500.5 -> ₺7.500,50
    try:
        v = float(value)
    except (TypeError, ValueError):
        v = 0.0
    return f"₺{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")



@api_bp.route('/login', methods=['POST'])
def api_login():
    """Kullanıcı Girişi ve JWT Oluşturma
    Bu endpoint, kullanıcının e-posta ve şifresini alarak kimliğini doğrular.
    Başarılı olursa, API'nin diğer endpoint'lerine erişim için kullanılacak bir JWT (access_token) döndürür.
    ---
    tags:
      - Kimlik Doğrulama (Authentication)
    parameters:
      - in: body
        name: body
        required: true
        schema:
          id: LoginCredentials
          required:
            - email
            - password
          properties:
            email:
              type: string
              description: Kullanıcının kayıtlı e-posta adresi.
              example: "sakin@ornek.com"
            password:
              type: string
              description: Kullanıcının şifresi.
              example: "123456"
    responses:
      200:
        description: Giriş başarılı. Token ve kullanıcı bilgileri döndürülür.
      400:
        description: Eksik JSON verisi veya eksik e-posta/şifre.
      401:
        description: Hatalı e-posta veya şifre.
      403:
        description: Kullanıcı hesabı henüz onaylanmamış veya pasif durumdadır.
    """
    
    data = request.get_json()
    if not data:
        return api_error("Eksik JSON verisi", 400)

    email = data.get('email', None)
    password = data.get('password', None)

    if not email or not password:
        return api_error("E-posta ve şifre zorunludur", 400)

    user = User.query.filter_by(email=email).first()

    if not user or not check_password_hash(user.password, password):
        return api_error("Hatalı e-posta veya şifre", 401)
    
    if not user.is_active:
        return api_error("Hesabınız henüz onaylanmamış veya pasif durumdadır", 403)

    # access_token = create_access_token(identity=user.id)
    access_token = create_access_token(identity=str(user.id))
    
    # Mobil uygulamaya gönderilecek zenginleştirilmiş kullanıcı verisi
    user_data = {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "apartment": {
            "id": user.apartment.id,
            "name": user.apartment.name
        },
        "block": {
            "id": user.block.id,
            "name": user.block.name
        } if user.block else None,
        "daire_no": user.daire_no,
        "phone_number": user.phone_number, # <-- YENİ EKLENDİ
        "registration_date_string": user.created_at.strftime('%d.%m.%Y') # <-- YENİ EKLENDİ
    }
    
    # Başarılı cevap olarak token'ı ve kullanıcı bilgilerini döndür.
    return api_success({
        "access_token": access_token,
        "user": user_data
    })

# =================================================================
# YENİ: KAYIT EKRANI İÇİN APARTMANLARI LİSTELEYEN ENDPOINT
# =================================================================
@api_bp.route('/apartments', methods=['GET'])
def get_apartments():
    """Kayıt Ekranı İçin Apartmanları Listeler
    Sistemdeki tüm apartmanların ID ve isimlerini döndürür. Mobil uygulamanın
    kayıt ekranındaki 'Apartman Seçin' listesini doldurmak için kullanılır.
    Bu endpoint public'tir ve token (kimlik doğrulama) gerektirmez.
    ---
    tags:
      - Public & Helpers
    responses:
      200:
        description: Apartman listesi başarıyla döndürüldü.
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: true
            data:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: integer
                    example: 1
                  name:
                    type: string
                    example: "Blue Life-1"
      500:
        description: Sunucu tarafında bir hata oluştu.
    """
    try:
        apartments = Apartment.query.order_by(Apartment.name).all()
        
        results = []
        for apt in apartments:
            results.append({
                "id": apt.id,
                "name": apt.name
            })
            
        return api_success(results)
        
    except Exception as e:
        current_app.logger.error(f"Apartman listesi çekilirken hata: {e}")
        return api_error("Apartman listesi alınırken bir sunucu hatası oluştu.", 500)

@api_bp.route('/apartments/<int:apartment_id>/blocks', methods=['GET'])
def get_blocks_for_apartment(apartment_id):
    """Bir Apartmana Ait Blokları Listeler
    URL'de belirtilen apartman ID'sine ait tüm blokların listesini döndürür.
    Mobil uygulamanın kayıt ekranındaki 'Blok Seçin' listesini dinamik olarak
    doldurmak için kullanılır. Public'tir ve token gerektirmez.
    ---
    tags:
      - Public & Helpers
    parameters:
      - name: apartment_id
        in: path
        type: integer
        required: true
        description: Blokları listelenecek olan apartmanın ID'si.
    responses:
      200:
        description: Blok listesi başarıyla döndürüldü.
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: true
            data:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: integer
                    example: 101
                  name:
                    type: string
                    example: "G-1 Blok"
      404:
        description: Belirtilen apartment_id ile bir apartman bulunamadı.
      500:
        description: Sunucu tarafında bir hata oluştu.
    """
    try:
        # Apartmanın var olup olmadığını kontrol et (opsiyonel ama iyi bir pratik)
        apartment = Apartment.query.get_or_404(apartment_id)
        
        blocks = Block.query.filter_by(apartment_id=apartment.id).order_by(Block.name).all()
        
        results = []
        for block in blocks:
            results.append({
                "id": block.id,
                "name": block.name
            })
            
        return api_success(results)
        
    except Exception as e:
        current_app.logger.error(f"Apartman blokları çekilirken hata (Apartment ID: {apartment_id}): {e}")
        return api_error("Blok listesi alınırken bir sunucu hatası oluştu.", 500)


@api_bp.route('/announcements', methods=['GET'])
@jwt_required()
def get_announcements():
    """Apartmana Ait Duyuruları Listeler
    Giriş yapmış kullanıcının apartmanına ait olan tüm duyuruları, en yeniden
    eskiye doğru ve sayfalanmış olarak listeler. Bu endpoint'i kullanmak için
    geçerli bir JWT (access_token) gereklidir.
    ---
    tags:
      - Duyurular (Announcements)
    security:
      - bearerAuth: []
    parameters:
      - name: page
        in: query
        type: integer
        required: false
        description: Sonuçların hangi sayfasının getirileceği. Varsayılan değer 1'dir.
    responses:
      200:
        description: Duyuru listesi ve sayfalama bilgileri başarıyla döndürüldü.
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
              properties:
                announcements:
                  type: array
                  items:
                    type: object
                    properties:
                      id:
                        type: integer
                      title:
                        type: string
                      content:
                        type: string
                      creator_name:
                        type: string
                      created_at:
                        type: string
                        format: date-time
                      created_at_display:
                        type: string
                pagination:
                  type: object
                  properties:
                    current_page:
                      type: integer
                    total_pages:
                      type: integer
                    has_next:
                      type: boolean
                    has_prev:
                      type: boolean
                    total_items:
                      type: integer
      401:
        description: Geçerli bir JWT (access_token) sağlanmadı.
      404:
        description: Token'a ait kullanıcı bulunamadı.
    """
    
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    if not user:
        return api_error("Kullanıcı bulunamadı", 404)

    # 1. URL'den sayfa numarasını al
    page = request.args.get('page', 1, type=int)
    per_page = 15

    # 2. .all() yerine .paginate() kullan
    pagination = Announcement.query.filter_by(
        apartment_id=user.apartment_id
    ).order_by(Announcement.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    announcements_on_page = pagination.items
    
    # 3. Sadece o sayfadaki duyuruları JSON formatına çevir
    results = []
    for ann in announcements_on_page:
        results.append({
            "id": ann.id,
            "title": ann.title,
            "content": ann.content,
            "creator_name": ann.creator.name,
            "created_at": ann.created_at.isoformat(), # Bu satır ham data olarak kalmalı
            "created_at_display": ann.created_at.strftime('%d %B %Y, %H:%M') # YENİ EKLENEN FORMATLI ALAN
        })
        
    # 4. Yanıtı, hem duyuru listesini hem de sayfalama bilgilerini içerecek şekilde oluştur
    data_payload = {
        "announcements": results,
        "pagination": {
            "current_page": pagination.page,
            "total_pages": pagination.pages,
            "has_next": pagination.has_next,
            "has_prev": pagination.has_prev,
            "total_items": pagination.total
        }
    }
    
    return api_success(data_payload)


@api_bp.route('/dues', methods=['GET'])
@jwt_required()
def get_dues():
    """Kullanıcının Aidatlarını Listeler
    Giriş yapmış kullanıcının kendisine atanmış tüm aidat borçlarını, en yeniden
    eskiye doğru ve sayfalanmış olarak listeler. Ayrıca ödenmemiş toplam borç
    tutarını da döndürür. Geçerli bir JWT (access_token) gereklidir.
    ---
    tags:
      - Aidat İşlemleri (Dues)
    security:
      - bearerAuth: []
    parameters:
      - name: page
        in: query
        type: integer
        required: false
        description: Sonuçların hangi sayfasının getirileceği. Varsayılan değer 1'dir.
    responses:
      200:
        description: Aidat listesi, toplam borç ve sayfalama bilgileri başarıyla döndürüldü.
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
              properties:
                total_debt:
                  type: number
                total_debt_display:
                  type: string
                dues_list:
                  type: array
                  items:
                    type: object
                    properties:
                      id:
                        type: integer
                      description:
                        type: string
                      amount:
                        type: number
                      due_date:
                        type: string
                        format: date
                      status:
                        type: string
                      period:
                        type: string
                      amount_display:
                        type: string
                pagination:
                  type: object
                  properties:
                    current_page:
                      type: integer
                    total_pages:
                      type: integer
                    has_next:
                      type: boolean
                    has_prev:
                      type: boolean
                    total_items:
                      type: integer
      401:
        description: Geçerli bir JWT (access_token) sağlanmadı.
      404:
        description: Token'a ait kullanıcı bulunamadı.
    """
    
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    if not user:
        return api_error("Kullanıcı bulunamadı", 404)

    # 1. URL'den sayfa numarasını al (?page=2 gibi). Varsayılan: 1. sayfa.
    page = request.args.get('page', 1, type=int)
    per_page = 15 # Mobil uygulama için sayfa başına 15-20 öğe daha uygun olabilir

    # 2. .all() yerine .paginate() kullanarak sadece ilgili sayfadaki aidatları çek.
    pagination = Dues.query.filter_by(user_id=current_user_id) \
        .order_by(Dues.due_date.desc()) \
        .paginate(page=page, per_page=per_page, error_out=False)
    
    dues_on_page = pagination.items
    today = datetime.utcnow().date()
    
    # 3. Aidat listesini JSON'a uygun bir formata dönüştür.
    dues_results = []
    for due in dues_on_page:
        status = "Ödendi"
        if not due.is_paid:
            status = "Gecikmede" if due.due_date < today else "Ödenmedi"
        dues_results.append({
            "id": due.id,
            "description": due.description,
            "amount": due.amount,
            "due_date": due.due_date.isoformat(),
            "status": status,
            "period": due.due_date.strftime("%B %Y"),  # Dönem bilgisi
            "amount_display": format_tl(due.amount)
        })

    # Toplam borç hesaplaması aynı kalıyor.
    total_debt_query = db.session.query(func.sum(Dues.amount)).filter(
        Dues.user_id == current_user_id,
        Dues.is_paid == False
    ).scalar()
    total_debt = total_debt_query or 0.0
        
    # 4. Mobil uygulamaya hem aidat listesini hem de sayfalama bilgilerini gönder.
    data_payload = {
        "total_debt": round(total_debt, 2),
        "total_debt_display": format_tl(total_debt),
        "dues_list": dues_results,
        "pagination": {
            "current_page": pagination.page,
            "total_pages": pagination.pages,
            "has_next": pagination.has_next,
            "has_prev": pagination.has_prev,
            "total_items": pagination.total
        }
    }
    return api_success(data_payload)

# === YENİ FONKSİYON SONU ===
# =================================================================
# YENİ: MOBİL İÇİN AİDAT DEKONTU YÜKLEME ENDPOINT'İ
# =================================================================
@api_bp.route('/dues/<int:dues_id>/receipt', methods=['POST'])
@jwt_required()
def upload_dues_receipt(dues_id):
    """Bir Aidat İçin Dekont Yükler
    URL'de belirtilen aidat borcu için bir dekont dosyası (resim veya PDF) yükler.
    İstek 'multipart/form-data' formatında olmalıdır. Dosya 'file' anahtarıyla
    gönderilmelidir. Yüklenen dekont yönetici onayına düşer.
    ---
    tags:
      - Aidat İşlemleri (Dues)
    security:
      - bearerAuth: []
    consumes:
      - multipart/form-data
    parameters:
      - name: dues_id
        in: path
        type: integer
        required: true
        description: Dekontun yükleneceği aidat borcunun ID'si.
      - name: file
        in: formData
        type: file
        required: true
        description: Yüklenecek dekont dosyası (jpg, png, pdf vb.).
    responses:
      200:
        description: Dekont başarıyla yüklendi ve yönetici onayına gönderildi.
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
              properties:
                dues_id:
                  type: integer
                receipt_url:
                  type: string
                upload_date:
                  type: string
                  format: date-time
      400:
        description: İstekte dosya bulunamadı veya dosya seçilmedi.
      401:
        description: Geçerli bir JWT (access_token) sağlanmadı.
      403:
        description: Kullanıcının bu aidat borcuna erişim yetkisi yok.
      404:
        description: Token'a ait kullanıcı veya belirtilen aidat borcu bulunamadı.
      500:
        description: Dosya GCS'e yüklenirken bir sunucu hatası oluştu.
    """
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    if not user:
        return api_error("Kullanıcı bulunamadı", 404)

    # 1. İlgili aidat borcunu bul
    dues = Dues.query.get_or_404(dues_id)

    # 2. Yetki kontrolü: Bu aidat bu kullanıcıya mı ait?
    if dues.user_id != user.id:
        return api_error("Bu aidat borcuna erişim veya işlem yapma yetkiniz yok.", 403)

    # 3. Dosyanın istekte olup olmadığını kontrol et
    if 'file' not in request.files:
        return api_error("İstekte 'file' adında bir dosya bulunamadı.", 400)
    
    file = request.files['file']
    if file.filename == '':
        return api_error("Dosya seçilmedi.", 400)

    # 4. Dosyayı Google Cloud Storage'a 'receipts' klasörüne yükle
    file_url = upload_to_gcs(file, 'receipts')
    if not file_url:
        return api_error("Dekont yüklenirken bir sunucu hatası oluştu.", 500)

    # 5. Veritabanındaki ilgili aidat kaydını güncelle
    dues.receipt_filename = file_url
    dues.receipt_upload_date = datetime.utcnow()
    # Not: Otomatik onaylama mantığı (Document AI) şu an için sadece web'de.
    # Burada sadece yükleyip yönetici onayına düşürüyoruz.
    db.session.commit()

    # 6. Başarılı olduğuna dair JSON yanıtı dön
    response_data = {
        "dues_id": dues.id,
        "receipt_url": dues.receipt_filename,
        "upload_date": dues.receipt_upload_date.isoformat()
    }
    
    return api_success(response_data, "Dekont başarıyla yüklendi ve yönetici onayına gönderildi.", 200)
# === YENİ EKLENEN FONKSİYON ===
@api_bp.route('/requests', methods=['GET'])
@jwt_required()
def get_requests():
    """Kullanıcının Taleplerini Listeler
    Giriş yapmış kullanıcının kendi oluşturduğu tüm talepleri (istek/şikayet)
    sayfalanmış olarak listeler. Geçerli bir JWT (access_token) gereklidir.
    ---
    tags:
      - Talepler (Requests)
    security:
      - bearerAuth: []
    parameters:
      - name: page
        in: query
        type: integer
        required: false
        description: Sonuçların hangi sayfasının getirileceği. Varsayılan değer 1'dir.
    responses:
      200:
        description: Talep listesi ve sayfalama bilgileri başarıyla döndürüldü.
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
              properties:
                requests:
                  type: array
                  items:
                    type: object
                    properties:
                      id:
                        type: integer
                      title:
                        type: string
                      description:
                        type: string
                      status:
                        type: string
                        example: "Beklemede"
                      created_at:
                        type: string
                        format: date-time
                      updated_at:
                        type: string
                        format: date-time
                      reply:
                        type: string
                        nullable: true
                      category:
                        type: string
                      priority:
                        type: string
                      location:
                        type: string
                      attachment_url:
                        type: string
                        nullable: true
                      status_display:
                        type: object
                        properties:
                          text:
                            type: string
                          color:
                            type: string
                pagination:
                  type: object
                  properties:
                    current_page:
                      type: integer
                    total_pages:
                      type: integer
      401:
        description: Geçerli bir JWT (access_token) sağlanmadı veya geçersiz.
    """

    def to_utc_iso(dt):
        if dt is None:
            return None
        # DB'den naive UTC geliyorsa tz atayalım; yoksa UTC'ye dönüştürelim
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        # '+00:00' yerine 'Z'
        return dt.isoformat().replace("+00:00", "Z")

    # Kimliği güvenli şekilde int'e çevir
    raw_identity = get_jwt_identity()
    try:
        current_user_id = int(raw_identity)
    except (TypeError, ValueError):
        return api_error("Geçersiz kimlik.", 401)

    # Sayfalama
    page = request.args.get('page', 1, type=int)
    per_page = 15

    pagination = (
        RequestModel.query
        .filter_by(user_id=current_user_id)
        .order_by(RequestModel.created_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    requests_on_page = pagination.items
    results = []

    # Status -> renk seçimi
    def choose_color(status_text: str) -> str:
        s = (status_text or "").strip().upper()
        if s in ("ISLEMDE", "IN_PROGRESS"):
            return "warning"
        if s in ("TAMAMLANDI", "DONE", "COMPLETED"):
            return "success"
        if s in ("REDDEDILDI", "REJECTED", "CANCELLED"):
            return "error"
        if s in ("YENI", "NEW", "BEKLEMEDE", "PENDING"):
            return "info"
        return "secondary"

    for req in requests_on_page:
        # status güvenli okuma
        if getattr(req, "status", None) is None:
            status_value = "Bilinmiyor"
        else:
            status_value = getattr(req.status, "value", req.status) or "Bilinmiyor"

        # updated_at boş olabilir -> created_at'a düş
        updated_dt = getattr(req, "updated_at", None) or req.created_at

        status_display = {
            "text": status_value,
            "color": choose_color(status_value)
        }

        results.append({
            "id": req.id,
            "title": req.title,
            "description": req.description,
            "status": status_value,
            # >>> Burada artık timezone-aware UTC 'Z' ile dönüyoruz
            "created_at": to_utc_iso(req.created_at),
            "updated_at": to_utc_iso(updated_dt),
            "reply": req.reply,
            "category": req.category,
            "priority": req.priority,
            "location": req.location,
            "attachment_url": req.attachment_url,

            # Legacy (görsel için server-side format). Mobilin bunları kullanmasına gerek yok.
            "created_at_display": req.created_at.strftime('%d %B %Y, %H:%M'),
            "updated_at_display": updated_dt.strftime('%d %B %Y, %H:%M'),

            "status_display": status_display
        })

    data_payload = {
        "requests": results,
        "pagination": {
            "current_page": pagination.page,
            "total_pages": pagination.pages,
            "has_next": pagination.has_next,
            "has_prev": pagination.has_prev,
            "total_items": pagination.total
        }
    }

    return api_success(data_payload)


@api_bp.route('/requests/options', methods=['GET'])
@jwt_required()
def get_request_options():
    """Yeni Talep İçin Seçenekleri Getirir
    Mobil uygulamanın 'Yeni Talep Oluştur' ekranındaki Kategori, Öncelik ve Konum
    seçim kutularını doldurmak için gereken verileri listeler.
    Geçerli bir JWT (access_token) gereklidir.
    ---
    tags:
      - Talepler (Requests)
    security:
      - bearerAuth: []
    responses:
      200:
        description: Talep seçenekleri başarıyla döndürüldü.
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
              properties:
                categories:
                  type: array
                  items: &OptionItem
                    type: object
                    properties:
                      key:
                        type: string
                      value:
                        type: string
                priorities:
                  type: array
                  items: *OptionItem
                locations:
                  type: array
                  items: *OptionItem
      401:
        description: Geçerli bir JWT (access_token) sağlanmadı.
    """
    # Bu listeler, create_request fonksiyonunuzdaki listelerle aynıdır.
    CATEGORY_MAP = {"ariza": "Arıza", "bakim": "Bakım", "yeni_talep": "Yeni talep", "diger": "Diğer"}
    PRIORITY_MAP = {"dusuk": "Düşük", "orta": "Orta", "yuksek": "Yüksek"}
    LOCATION_MAP = {
        "asansor": "Asansör", "elektrik": "Elektrik", "su": "Su Tesisatı", 
        "dogalgaz": "Doğalgaz / Kazan", "otopark": "Otopark", "bahce": "Bahçe / Peyzaj", 
        "guvenlik": "Güvenlik", "merdiven": "Merdiven / Ortak Alan", "cati": "Çatı", 
        "dis_cephe": "Dış Cephe", "oyun_alani": "Oyun Alanı", "diger": "Diğer"
    }

    # Mobil uygulamanın kolayca kullanabilmesi için veriyi formatla
    def format_for_mobile(options_map):
        return [{"key": key, "value": value} for key, value in options_map.items()]

    response_data = {
        "categories": format_for_mobile(CATEGORY_MAP),
        "priorities": format_for_mobile(PRIORITY_MAP),
        "locations": format_for_mobile(LOCATION_MAP)
    }
    
    return api_success(response_data)

# app/routes/api.py

# api.py dosyanızdaki mevcut create_request fonksiyonunu bununla değiştirin

@api_bp.route('/requests', methods=['POST'])
@jwt_required()
def create_request():
    """Yeni Talep (İstek/Şikayet) Oluşturur
    Mobil uygulamadan gelen verilerle yeni bir talep oluşturur. Bu endpoint
    'multipart/form-data' formatında veri kabul eder, bu sayede hem talep
    bilgileri hem de (isteğe bağlı) bir dosya eki aynı anda gönderilebilir.
    Geçerli bir JWT (access_token) gereklidir.
    ---
    tags:
      - Talepler (Requests)
    security:
      - bearerAuth: []
    consumes:
      - multipart/form-data
    parameters:
      - name: title
        in: formData
        type: string
        required: true
        description: Talebin başlığı.
      - name: description
        in: formData
        type: string
        required: true
        description: Talebin detaylı açıklaması.
      - name: category
        in: formData
        type: string
        required: true
        description: "Talebin kategorisi. ('/requests/options' endpoint'inden gelen 'key' değerlerinden biri olmalıdır)."
        example: "ariza"
      - name: priority
        in: formData
        type: string
        required: true
        description: "Talebin önceliği. ('/requests/options' endpoint'inden gelen 'key' değerlerinden biri olmalıdır)."
        example: "orta"
      - name: location
        in: formData
        type: string
        required: true
        description: "Talebin ilgili olduğu konum. ('/requests/options' endpoint'inden gelen 'key' değerlerinden biri olmalıdır)."
        example: "asansor"
      - name: attachment
        in: formData
        type: file
        required: false
        description: "Taleple ilgili isteğe bağlı dosya eki (resim, pdf vb.)."
    responses:
      201:
        description: Talep başarıyla oluşturuldu.
      400:
        description: Zorunlu alanlardan biri eksik veya geçersiz bir anahtar kelime gönderildi.
      401:
        description: Geçerli bir JWT (access_token) sağlanmadı.
      404:
        description: Token'a ait kullanıcı bulunamadı.
      415:
        description: İstek 'multipart/form-data' formatında değil.
      500:
        description: Dosya yüklenirken veya veritabanına kayıt sırasında sunucu hatası oluştu.
    """
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    if not user:
        return api_error("Kullanıcı bulunamadı", 404)

    if not request.form:
        return api_error("İstek 'multipart/form-data' formatında olmalıdır.", 415)

    form_data = request.form
    file_obj = request.files.get('attachment')

    title = form_data.get('title', '').strip()
    description = form_data.get('description', '').strip()
    
    category_key = form_data.get('category', '').strip()
    priority_key = form_data.get('priority', '').strip()
    location_key = form_data.get('location', '').strip()
    
    # --- DEĞİŞİKLİK BURADA BAŞLIYOR ---
    # Artık 'location_other' alanını okumuyoruz.

    if not all([title, description, category_key, priority_key, location_key]):
        return api_error("Başlık, açıklama, kategori, öncelik ve konum alanları zorunludur.", 400)
    
    # Geçerli seçenekleri tanımla
    CATEGORY_MAP = {"ariza": "Arıza", "bakim": "Bakım", "yeni_talep": "Yeni talep", "diger": "Diğer"}
    PRIORITY_MAP = {"dusuk": "Düşük", "orta": "Orta", "yuksek": "Yüksek"}
    LOCATION_MAP = {
        "asansor": "Asansör", "elektrik": "Elektrik", "su": "Su Tesisatı", 
        "dogalgaz": "Doğalgaz / Kazan", "otopark": "Otopark", "bahce": "Bahçe / Peyzaj", 
        "guvenlik": "Güvenlik", "merdiven": "Merdiven / Ortak Alan", "cati": "Çatı", 
        "dis_cephe": "Dış Cephe", "oyun_alani": "Oyun Alanı", "diger": "Diğer"
    }

    # Gelen anahtar kelimelerin geçerli olup olmadığını kontrol et
    if category_key not in CATEGORY_MAP:
        return api_error(f"Geçersiz kategori anahtarı: {category_key}", 400)
    if priority_key not in PRIORITY_MAP:
        return api_error(f"Geçersiz öncelik anahtarı: {priority_key}", 400)
    if location_key not in LOCATION_MAP:
        return api_error(f"Geçersiz konum anahtarı: {location_key}", 400)

    # Veritabanına kaydedilecek etiketleri (value) haritadan al
    category_label = CATEGORY_MAP[category_key]
    priority_label = PRIORITY_MAP[priority_key]
    location_value = LOCATION_MAP[location_key]

    # Dosya yükleme mantığı
    attachment_url = None
    if file_obj and file_obj.filename:
        uploaded_url = upload_to_gcs(file_obj, 'requests')
        if not uploaded_url:
            return api_error("Ek dosya yüklenirken bir sunucu hatası oluştu.", 500)
        attachment_url = uploaded_url

    # Veritabanına kaydetme mantığı
    try:
        new_request = RequestModel(
            title=title,
            description=description,
            category=category_label,
            priority=priority_label,
            location=location_value,
            attachment_url=attachment_url,
            user_id=current_user_id,
            apartment_id=user.apartment_id
        )
        db.session.add(new_request)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"API - Talep oluşturma hatası: {e}")
        return api_error("Talep oluşturulurken veritabanı hatası oluştu.", 500)

    # Yanıt hazırlama
    response_data = {
        "request": {
            "id": new_request.id,
            "title": new_request.title,
            "description": new_request.description,
            "status": new_request.status.value if new_request.status else "Bilinmiyor",
            "created_at": new_request.created_at.isoformat(),
            "category": new_request.category,
            "priority": new_request.priority,
            "location": new_request.location,
            "attachment_url": new_request.attachment_url
        }
    }
    
    return api_success(response_data, "Talebiniz başarıyla oluşturuldu.", 201)


@api_bp.route('/documents', methods=['GET'])
@jwt_required()
def get_documents():
    """Kullanıcının Belgelerini Listeler
    Giriş yapmış kullanıcının sisteme yüklediği tüm kişisel belgeleri
    (kira kontratı, ikametgah vb.) listeler.
    Geçerli bir JWT (access_token) gereklidir.
    ---
    tags:
      - Belgeler (Documents)
    security:
      - bearerAuth: []
    responses:
      200:
        description: Belge listesi başarıyla döndürüldü.
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: integer
                  doc_type:
                    type: string
                    example: "Kira Kontratı"
                  filename:
                    type: string
                    description: "Belgenin GCS üzerindeki tam URL'i."
                  upload_date:
                    type: string
                    format: date-time
                  download_url:
                    type: string
                    description: "Belgeyi indirmek için kullanılacak API endpoint URL'i."
      401:
        description: Geçerli bir JWT (access_token) sağlanmadı."""
    
    current_user_id = get_jwt_identity()
    
    user_documents = Document.query.filter_by(
        user_id=current_user_id
    ).order_by(Document.upload_date.desc()).all()
    
    results = []
    for doc in user_documents:
        results.append({
            "id": doc.id,
            "doc_type": doc.doc_type,
            "filename": doc.filename,
            "upload_date": doc.upload_date.isoformat(),
            "download_url": url_for('api.download_document', document_id=doc.id, _external=True)
        })
        
    # GÜNCELLENDİ: Standart başarılı cevap formatı kullanıldı.
    return api_success(results)


@api_bp.route('/documents/<int:document_id>/download', methods=['GET'])
@jwt_required()
def download_document(document_id):
    """Belge İndirme Linki Alır
    Belirtilen ID'ye sahip belge için Google Cloud Storage üzerinde bulunan asıl dosya
    URL'ine bir yönlendirme (302 Redirect) yapar. Mobil uygulama veya tarayıcı bu
    yönlendirmeyi takip ederek dosyayı doğrudan GCS'ten indirir.
    Geçerli bir JWT (access_token) gereklidir.
    ---
    tags:
      - Belgeler (Documents)
    security:
      - bearerAuth: []
    parameters:
      - name: document_id
        in: path
        type: integer
        required: true
        description: İndirilecek olan belgenin ID'si.
    responses:
      302:
        description: "Başarılı. Yanıt, dosyanın gerçek konumuna (GCS URL) yönlendirme içerir."
      401:
        description: Geçerli bir JWT (access_token) sağlanmadı.
      403:
        description: "Kullanıcının bu belgeye erişim yetkisi yok (ne sahibi ne de admin)."
      404:
        description: Belirtilen ID ile bir belge bulunamadı.
    """
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    doc = Document.query.get_or_404(document_id)

    # Yetki kontrolü: Belge kullanıcıya ait mi VEYA kullanıcı admin mi?
    if doc.user_id != current_user_id and user.role != 'admin':
        return api_error("Bu belgeye erişim yetkiniz yok", 403)

    # Veritabanından GCS URL'ini al ve kullanıcıyı o adrese yönlendir.
    # Tarayıcı veya mobil uygulama bu yönlendirmeyi takip ederek dosyayı 
    # doğrudan GCS'ten indirecektir.
    return redirect(doc.filename)


@api_bp.route('/documents', methods=['POST'])
@jwt_required()
def upload_document():
    """Yeni Belge Yükler
    Kullanıcının yeni bir kişisel belge (kira kontratı, ikametgah vb.) yüklemesini sağlar.
    İstek 'multipart/form-data' formatında olmalıdır. Dosya 'file' anahtarıyla,
    belge türü ise 'doc_type' anahtarıyla gönderilmelidir.
    Geçerli bir JWT (access_token) gereklidir.
    ---
    tags:
      - Belgeler (Documents)
    security:
      - bearerAuth: []
    consumes:
      - multipart/form-data
    parameters:
      - name: doc_type
        in: formData
        type: string
        required: true
        description: "Yüklenen belgenin türü (örn: Kira Kontratı, İkametgah Belgesi, Su Faturası)."
      - name: file
        in: formData
        type: file
        required: true
        description: "Yüklenecek olan belge dosyası."
    responses:
      201:
        description: Belge başarıyla yüklendi ve veritabanına kaydedildi.
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
              properties:
                document:
                  type: object
                  properties:
                    id:
                      type: integer
                    doc_type:
                      type: string
                    filename:
                      type: string
                    upload_date:
                      type: string
                      format: date-time
      400:
        description: İstekte 'file' veya 'doc_type' alanı eksik.
      401:
        description: Geçerli bir JWT (access_token) sağlanmadı.
      404:
        description: Token'a ait kullanıcı bulunamadı.
      500:
        description: Dosya GCS'e yüklenirken bir sunucu hatası oluştu."""
    
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    if not user:
        return api_error("Kullanıcı bulunamadı", 404)

    if 'file' not in request.files:
        return api_error("İstekte dosya bulunamadı", 400)
    
    file = request.files['file']
    if file.filename == '':
        return api_error("Dosya seçilmedi", 400)

    doc_type = request.form.get('doc_type')
    if not doc_type:
        return api_error("Belge türü belirtilmelidir", 400)

    # === DEĞİŞEN BÖLÜM ===
    # Eski, sunucuya dosya kaydeden kod yerine GCS'e yükleme yapıyoruz.
    file_url = upload_to_gcs(file, 'documents')
    if not file_url:
        return api_error("Dosya yüklenirken bir sunucu hatası oluştu.", 500)
    # === DEĞİŞİKLİK SONU ===

    new_document = Document(
        filename=file_url, # Veritabanına artık dosya adı yerine GCS URL'ini kaydediyoruz.
        doc_type=doc_type,
        user_id=current_user_id,
        apartment_id=user.apartment_id
    )
    db.session.add(new_document)
    db.session.commit()

    response_data = {
        "msg": "Belge başarıyla yüklendi.",
        "document": {
            "id": new_document.id,
            "doc_type": new_document.doc_type,
            "filename": new_document.filename, # Bu artık tam URL
            "upload_date": new_document.upload_date.isoformat()
            # Download URL'i artık filename'in kendisi olduğu için ayrıca göndermeye gerek yok.
        }
    }
    return api_success(response_data, 201)

@api_bp.route('/polls', methods=['GET'])
@jwt_required()
def get_polls():
    """Apartmana Ait Anketleri Listeler
    Giriş yapmış kullanıcının apartmanına ait olan tüm aktif anketleri,
    sayfalanmış olarak listeler. Kullanıcının hangi anketlere daha önce oy
    kullandığı 'has_voted' alanı ile belirtilir.
    Geçerli bir JWT (access_token) gereklidir.
    ---
    tags:
      - Anketler (Polls)
    security:
      - bearerAuth: []
    parameters:
      - name: page
        in: query
        type: integer
        required: false
        description: Sonuçların hangi sayfasının getirileceği. Varsayılan değer 1'dir.
    responses:
      200:
        description: Anket listesi ve sayfalama bilgileri başarıyla döndürüldü.
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
              properties:
                polls:
                  type: array
                  items:
                    type: object
                    properties:
                      id:
                        type: integer
                      question:
                        type: string
                      created_at:
                        type: string
                        format: date-time
                      has_voted:
                        type: boolean
                      options:
                        type: array
                        items:
                          type: object
                          properties:
                            id:
                              type: integer
                            text:
                              type: string
                pagination:
                  type: object
                  properties:
                    current_page:
                      type: integer
                    total_pages:
                      type: integer
      401:
        description: Geçerli bir JWT (access_token) sağlanmadı.
      404:
        description: Token'a ait kullanıcı bulunamadı.
    """
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    if not user:
        return api_error("Kullanıcı bulunamadı", 404)

    page = request.args.get('page', 1, type=int)
    per_page = 15

    pagination = Poll.query.filter_by(
        apartment_id=user.apartment_id,
        is_active=True
    ).order_by(Poll.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    polls_on_page = pagination.items
    
    voted_poll_ids = {vote.poll_id for vote in Vote.query.filter_by(user_id=current_user_id).all()}
    
    results = []
    for poll in polls_on_page:
        # Her anketin seçeneklerini bir liste olarak hazırla
        options_list = []
        for option in poll.options.all():
            options_list.append({
                "id": option.id,
                "text": option.text
            })
        
        results.append({
            "id": poll.id,
            "question": poll.question,
            "created_at": poll.created_at.isoformat(),
            "created_at_display": poll.created_at.strftime('%d %B %Y, %H:%M'), # <-- YENİ EKLENDİ
            "has_voted": poll.id in voted_poll_ids,
            "options": options_list
        })
        
    data_payload = {
        "polls": results,
        "pagination": {
            "current_page": pagination.page,
            "total_pages": pagination.pages,
            "has_next": pagination.has_next,
            "has_prev": pagination.has_prev,
            "total_items": pagination.total
        }
    }
    
    return api_success(data_payload)


@api_bp.route('/polls/<int:poll_id>', methods=['GET'])
@jwt_required()
def get_poll_details(poll_id):
    """Tek Bir Anketin Detaylarını Getirir
    Oy kullanma ekranı için, URL'de belirtilen ID'ye sahip anketin sorusunu
    ve oy verilebilecek seçeneklerini listeler.
    Geçerli bir JWT (access_token) gereklidir.
    ---
    tags:
      - Anketler (Polls)
    security:
      - bearerAuth: []
    parameters:
      - name: poll_id
        in: path
        type: integer
        required: true
        description: Detayları görüntülenecek olan anketin ID'si.
    responses:
      200:
        description: Anket detayları başarıyla döndürüldü.
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
              properties:
                id:
                  type: integer
                question:
                  type: string
                options:
                  type: array
                  items:
                    type: object
                    properties:
                      id:
                        type: integer
                      text:
                        type: string
      401:
        description: Geçerli bir JWT (access_token) sağlanmadı.
      403:
        description: Kullanıcının bu ankete erişim yetkisi yok (farklı apartman).
      404:
        description: Token'a ait kullanıcı veya belirtilen ID'ye sahip anket bulunamadı."""
    
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    if not user:
        # GÜNCELLENDİ
        return api_error("Kullanıcı bulunamadı", 404)

    poll = Poll.query.get_or_404(poll_id)

    if poll.apartment_id != user.apartment_id:
        # GÜNCELLENDİ
        return api_error("Bu ankete erişim yetkiniz yok", 403)

    options_list = []
    for option in poll.options.all():
        options_list.append({
            "id": option.id,
            "text": option.text
        })
    
    # GÜNCELLENDİ
    response_data = {
        "id": poll.id,
        "question": poll.question,
        "options": options_list
    }
    return api_success(response_data)


@api_bp.route('/polls/<int:poll_id>/vote', methods=['POST'])
@jwt_required()
def submit_vote(poll_id):
    """Bir Ankete Oy Verir
    Belirtilen ankete, gönderilen seçenek ID'si ile oy verilmesini sağlar.
    Bir kullanıcı aynı ankete sadece bir kez oy verebilir.
    Geçerli bir JWT (access_token) gereklidir.
    ---
    tags:
      - Anketler (Polls)
    security:
      - bearerAuth: []
    parameters:
      - name: poll_id
        in: path
        type: integer
        required: true
        description: Oy kullanılacak olan anketin ID'si.
      - name: body
        in: body
        required: true
        schema:
          id: VotePayload
          required:
            - option_id
          properties:
            option_id:
              type: integer
              description: Oy verilecek seçeneğin ID'si.
    responses:
      201:
        description: Oy başarıyla kaydedildi.
      400:
        description: "Geçersiz istek (Anket aktif/süresi geçmiş değil, 'option_id' eksik veya formatı yanlış)."
      401:
        description: Geçerli bir JWT (access_token) sağlanmadı.
      403:
        description: Kullanıcının bu ankete erişim yetkisi yok (farklı apartman).
      404:
        description: Token'a ait kullanıcı, anket veya gönderilen seçenek ID'si bulunamadı.
      409:
        description: Kullanıcı bu ankete daha önce oy kullanmış."""
    
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    if not user:
        # GÜNCELLENDİ
        return api_error("Kullanıcı bulunamadı", 404)

    poll = Poll.query.get_or_404(poll_id)

    if poll.apartment_id != user.apartment_id:
        # GÜNCELLENDİ
        return api_error("Bu ankete erişim yetkiniz yok", 403)

    # Anket aktif mi?
    if not poll.is_active:
        return api_error("Bu anket artık aktif değil.", 400)

    # Anketin süresi dolmuş mu?
    if getattr(poll, "expiration_date", None) and datetime.utcnow() > poll.expiration_date:
        return api_error("Bu anketin oylama süresi dolmuştur.", 400)
    
    existing_vote = Vote.query.filter_by(user_id=current_user_id, poll_id=poll_id).first()
    if existing_vote:
        # GÜNCELLENDİ
        return api_error("Bu ankete daha önce oy kullandınız.", 409)

    data = request.get_json()
    if not data or 'option_id' not in data:
        # GÜNCELLENDİ
        return api_error("Geçersiz istek: 'option_id' gereklidir", 400)
    
    # option_id tipini int'e zorla
    try:
        option_id = int(data.get('option_id'))
    except (TypeError, ValueError):
        return api_error("Geçersiz 'option_id' formatı. Sayı olmalıdır.", 400)
    
    option = PollOption.query.filter_by(id=option_id, poll_id=poll_id).first()
    if not option:
        # GÜNCELLENDİ
        return api_error("Geçersiz seçenek ID'si", 404)

    new_vote = Vote(
        user_id=current_user_id,
        poll_id=poll_id,
        option_id=option_id
    )
    db.session.add(new_vote)
    db.session.commit()

    # GÜNCELLENDİ
    return api_success({"msg": "Oyunuz başarıyla kaydedildi."}, 201)

@api_bp.route('/polls/<int:poll_id>/results', methods=['GET'])
@jwt_required()
def get_poll_results(poll_id):
    """Bir Anketin Sonuçlarını Getirir
    Belirtilen ID'ye sahip anketin o anki sonuçlarını, her bir seçeneğin aldığı
    oy sayısını ve yüzdelik dağılımını döndürür.
    Geçerli bir JWT (access_token) gereklidir.
    ---
    tags:
      - Anketler (Polls)
    security:
      - bearerAuth: []
    parameters:
      - name: poll_id
        in: path
        type: integer
        required: true
        description: Sonuçları görüntülenecek olan anketin ID'si.
    responses:
      200:
        description: Anket sonuçları başarıyla döndürüldü.
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
              properties:
                id:
                  type: integer
                question:
                  type: string
                total_votes:
                  type: integer
                results:
                  type: array
                  items:
                    type: object
                    properties:
                      option_id:
                        type: integer
                      text:
                        type: string
                      votes:
                        type: integer
                      percentage:
                        type: number
      401:
        description: Geçerli bir JWT (access_token) sağlanmadı.
      403:
        description: Kullanıcının bu anket sonuçlarına erişim yetkisi yok.
      404:
        description: Token'a ait kullanıcı veya belirtilen ID'ye sahip anket bulunamadı."""
    
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    if not user:
        # GÜNCELLENDİ
        return api_error("Kullanıcı bulunamadı", 404)

    poll = Poll.query.get_or_404(poll_id)

    if poll.apartment_id != user.apartment_id:
        # GÜNCELLENDİ
        return api_error("Bu anketin sonuçlarına erişim yetkiniz yok", 403)

    total_votes = poll.votes.count()

    results_list = []
    for option in poll.options.all():
        vote_count = option.votes.count()
        percentage = (vote_count / total_votes * 100) if total_votes > 0 else 0
        results_list.append({
            "option_id": option.id,
            "text": option.text,
            "votes": vote_count,
            "percentage": round(percentage, 2)
        })
        
    # GÜNCELLENDİ
    response_data = {
        "id": poll.id,
        "question": poll.question,
        "total_votes": total_votes,
        "results": results_list
    }
    return api_success(response_data)


@api_bp.route('/craftsmen', methods=['GET'])
@jwt_required()
def get_craftsmen():
    """Anlaşmalı Ustaları Listeler
    Yönetici tarafından sisteme eklenmiş ve sakinin apartmanına ait olan
    tüm anlaşmalı ustaların (elektrikçi, tesisatçı vb.) listesini döndürür.
    Telefon numarası güvenlik nedeniyle bu endpoint'te paylaşılmaz.
    Geçerli bir JWT (access_token) gereklidir.
    ---
    tags:
      - Usta Rehberi (Craftsmen)
    security:
      - bearerAuth: []
    responses:
      200:
        description: Usta listesi başarıyla döndürüldü.
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: integer
                  specialty:
                    type: string
                    example: "Elektrik"
                  full_name:
                    type: string
                    example: "Ahmet Usta"
                  notes:
                    type: string
                    nullable: true
                    example: "Sadece hafta içi hizmet vermektedir."
      401:
        description: Geçerli bir JWT (access_token) sağlanmadı.
      404:
        description: Token'a ait kullanıcı bulunamadı."""
    
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    if not user:
        return api_error("Kullanıcı bulunamadı", 404)

    craftsmen_list = Craftsman.query.filter_by(
        apartment_id=user.apartment_id
    ).order_by(Craftsman.specialty).all()
    
    results = []
    for craftsman in craftsmen_list:
        results.append({
            "id": craftsman.id,
            "specialty": craftsman.specialty,
            "full_name": craftsman.full_name,
            "notes": craftsman.notes
        })
    return api_success(results)


@api_bp.route('/craftsmen/<int:craftsman_id>/request', methods=['POST'])
@jwt_required()
def request_craftsman_contact(craftsman_id):
    """Bir Ustanın İletişim Bilgisini Talep Eder
    Belirtilen ID'ye sahip ustanın iletişim bilgisinin görüntülenmesi için
    bir talep oluşturur ve bu talebi veritabanına kaydeder. Başarılı yanıtta,
    apartmana ait TÜM usta listesini yeniden döndürür, ancak bu sefer
    sadece talep edilen ustanın 'phone_number' alanı dolu gelir.
    Geçerli bir JWT (access_token) gereklidir.
    ---
    tags:
      - Usta Rehberi (Craftsmen)
    security:
      - bearerAuth: []
    parameters:
      - name: craftsman_id
        in: path
        type: integer
        required: true
        description: İletişim bilgisi talep edilen ustanın ID'si.
    responses:
      200:
        description: Talep başarıyla loglandı ve güncellenmiş usta listesi döndürüldü.
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: integer
                  specialty:
                    type: string
                  full_name:
                    type: string
                  notes:
                    type: string
                    nullable: true
                  phone_number:
                    type: string
                    nullable: true
                    description: "Sadece talep edilen usta için dolu gelir, diğerleri için null'dır."
      401:
        description: Geçerli bir JWT (access_token) sağlanmadı.
      403:
        description: Kullanıcının bu ustaya erişim yetkisi yok (farklı apartman).
      404:
        description: Token'a ait kullanıcı veya belirtilen ID'ye sahip usta bulunamadı.
      500:
        description: Talep loglanırken bir sunucu hatası oluştu.
    """
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    if not user:
        return api_error("Kullanıcı bulunamadı", 404)

    # Talep edilen ustanın varlığını ve yetkisini kontrol et
    craftsman_requested = Craftsman.query.get_or_404(craftsman_id)
    if craftsman_requested.apartment_id != user.apartment_id:
        return api_error("Bu ustaya erişim yetkiniz yok.", 403)

    # 1. Talep loglama işlemi (Bu kısım aynı kalıyor)
    try:
        log_entry = CraftsmanRequestLog(
            resident_id=user.id,
            craftsman_id=craftsman_id,
            apartment_id=user.apartment_id
        )
        db.session.add(log_entry)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Usta talep logu kaydedilirken hata: {e}")
        return api_error("İşlem sırasında bir sunucu hatası oluştu.", 500)

    all_craftsmen_in_apartment = Craftsman.query.filter_by(
        apartment_id=user.apartment_id
    ).order_by(Craftsman.specialty).all()
    
    results = []
    for craftsman in all_craftsmen_in_apartment:
        craftsman_data = {
            "id": craftsman.id,
            "specialty": craftsman.specialty,
            "full_name": craftsman.full_name,
            "notes": craftsman.notes,
            "phone_number": None 
        }
        

        if craftsman.id == craftsman_id:
            craftsman_data["phone_number"] = craftsman.phone_number
            
        results.append(craftsman_data)
        
    return api_success(results, msg="Talep oluşturuldu. Usta ile iletişime geçebilirsiniz.")

@api_bp.route('/financials/monthly_summary', methods=['GET'])
@jwt_required()
def get_monthly_summary_for_resident():
    """Aylık Finansal Özeti Getirir
    Giriş yapmış kullanıcının apartmanına ait, içinde bulunulan ayın gelir ve
    gider dökümünü listeler. Ayrıca apartmanın genel kasa bakiyesini de içerir.
    Geçerli bir JWT (access_token) gereklidir.
    ---
    tags:
      - Finansal (Financials)
    security:
      - bearerAuth: []
    responses:
      200:
        description: Aylık finansal özet başarıyla döndürüldü.
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
              properties:
                current_month_name:
                  type: string
                total_income:
                  type: number
                total_income_display:
                  type: string
                total_expense:
                  type: number
                total_expense_display:
                  type: string
                total_balance:
                  type: number
                total_balance_display:
                  type: string
                income_list:
                  type: array
                  items: &TransactionItem
                    type: object
                    properties:
                      id:
                        type: integer
                      description:
                        type: string
                      amount:
                        type: number
                      date_display:
                        type: string
                      amount_display:
                        type: string
                expense_list:
                  type: array
                  items:
                    allOf:
                      - *TransactionItem
                      - type: object
                        properties:
                          invoice_url:
                            type: string
                            nullable: true
      400:
        description: Kullanıcı bir apartmana atanmamış.
      401:
        description: Geçerli bir JWT (access_token) sağlanmadı.
      404:
        description: Token'a ait kullanıcı bulunamadı.
      500:
        description: Veriler alınırken bir sunucu hatası oluştu.
    """
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    if not user:
        return api_error("Kullanıcı bulunamadı", 404)

    apartment_id = user.apartment_id
    if not apartment_id:
        return api_error("Kullanıcı bir apartmana atanmamış.", 400)

    try:
        today = datetime.utcnow()
        start_of_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        next_month = start_of_month.replace(day=28) + relativedelta(days=4)
        end_of_month = next_month - relativedelta(days=next_month.day)
        end_of_month = end_of_month.replace(hour=23, minute=59, second=59)


        transactions_in_month = Transaction.query.filter(
            Transaction.apartment_id == apartment_id,
            Transaction.transaction_date.between(start_of_month, end_of_month)
        ).order_by(Transaction.transaction_date.desc()).all()

        income_list = []
        expense_list = []
        total_income = 0.0
        total_expense = 0.0

        for t in transactions_in_month:
            item_data = {
                "id": t.id,
                "description": t.description,
                "amount": t.amount,
                "date_display": t.transaction_date.strftime('%d.%m.%Y'),
                "amount_display": format_tl(t.amount)
            }
            if t.amount > 0:
                income_list.append(item_data)
                total_income += t.amount
            else:
                invoice_url = None # Fatura URL'sini varsayılan olarak None yap
                
                if t.source_type == 'expense' and t.source_id is not None:
                    from app.models import Expense
                    expense_record = Expense.query.get(t.source_id)
                    if expense_record:
                        invoice_url = expense_record.invoice_filename
                
                item_data['invoice_url'] = invoice_url
                expense_list.append(item_data)
                total_expense += t.amount
        # ===== YENİ EKLENEN TOPLAM BAKİYE HESAPLAMASI =====
        total_balance_query = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.apartment_id == apartment_id
        ).scalar()
        total_balance = total_balance_query or 0.0

        response_data = {
            "current_month_name": start_of_month.strftime('%B %Y'),
            "total_income": round(total_income, 2),
            "total_income_display": format_tl(total_income),
            "total_expense": round(abs(total_expense), 2),
            "total_expense_display": format_tl(abs(total_expense)),
            "income_list": income_list,
            "expense_list": expense_list,
            "total_balance": round(total_balance, 2),
            "total_balance_display": format_tl(total_balance)
        }

        return api_success(response_data)

    except Exception as e:
        current_app.logger.error(f"API - Aylık özet çekilirken hata: {e}")
        return api_error("Aylık özet verileri alınırken bir sunucu hatası oluştu.", 500)


@api_bp.route('/register', methods=['POST'])
def api_register():
    """Yeni Kullanıcı Kaydı Oluşturur
    Mobil uygulamadan gelen kullanıcı bilgileriyle yeni bir sakin hesabı oluşturur.
    Başarılı kayıt sonrası, kullanıcıya bir e-posta doğrulama linki gönderilir ve
    hesap yönetici onayı için beklemeye alınır. Bu endpoint public'tir.
    ---
    tags:
      - Kimlik Doğrulama (Authentication)
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        description: "Yeni kullanıcı için kayıt bilgileri."
        schema:
          id: RegisterPayload
          required:
            - first_name
            - last_name
            - email
            - password
            - confirm
            - apartment_id
            - daire_no
            - accept_terms
            - accept_privacy
            - accept_kvkk
          properties:
            first_name:
              type: string
              example: "Ahmet"
            last_name:
              type: string
              example: "Yılmaz"
            email:
              type: string
              format: email
              example: "yeni.sakin@ornek.com"
            password:
              type: string
              format: password
              example: "GucluSifre123"
            confirm:
              type: string
              format: password
              example: "GucluSifre123"
            phone_number:
              type: string
              nullable: true
              example: "5551234567"
            apartment_id:
              type: integer
              description: "'/apartments' endpoint'inden alınan apartman ID'si."
              example: 1
            block_id:
              type: integer
              nullable: true
              description: "'/apartments/{id}/blocks' endpoint'inden alınan blok ID'si (isteğe bağlı)."
              example: 101
            daire_no:
              type: string
              example: "15"
            accept_terms:
              type: boolean
              description: "Kullanım Şartlarını kabul ettiğini belirtir."
              example: true
            accept_privacy:
              type: boolean
              description: "Gizlilik Politikasını kabul ettiğini belirtir."
              example: true
            accept_kvkk:
              type: boolean
              description: "KVKK metnini kabul ettiğini belirtir."
              example: true
    responses:
      201:
        description: "Kayıt başarılı. Yeni oluşturulan kullanıcı verisi döndürülür."
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
              properties:
                user:
                  type: object
                  description: "Oluşturulan yeni kullanıcı objesi"
      400:
        description: "Form validasyonu başarısız oldu (eksik alan, şifreler uyuşmuyor vb.)."
      409:
        description: "Bu e-posta adresi zaten sistemde kayıtlı."
      500:
        description: "Kayıt sırasında beklenmedik bir sunucu hatası oluştu."
    """
    form = RegisterForm(meta={'csrf': False})
    form.apartment_id.choices = [(apt.id, apt.name) for apt in Apartment.query.order_by(Apartment.name).all()]
    form.block_id.choices = [(block.id, block.name) for block in Block.query.order_by(Block.name).all()]

    form_data = None
    if request.is_json:
        form_data = MultiDict(request.get_json())
    else:
        form_data = request.form

    form.process(formdata=form_data)

    if form.validate():
        try:
            if User.query.filter_by(email=form.email.data.lower()).first():
                return api_error("Bu e-posta adresi zaten kayıtlı.", 409)

            hashed_password = generate_password_hash(form.password.data)

            full_name = f"{form.first_name.data} {form.last_name.data}".strip()

            new_user = User(
                email=form.email.data.lower(),
                password=hashed_password,
                name=full_name,
                apartment_id=form.apartment_id.data,
                block_id=form.block_id.data or None,
                daire_no=form.daire_no.data,
                phone_number=form.phone_number.data,
                is_active=False,
                is_email_verified=False,
                role="resident"
            )
            db.session.add(new_user)
            db.session.commit()

            # --- DÜZELTİLMİŞ KISIM: KULLANICIYA AKTİVASYON E-POSTASI GÖNDER ---
            try:
                token = new_user.generate_confirmation_token()
                confirm_url = url_for('auth.confirm_email', token=token, _external=True)
                send_email(
                    to=new_user.email,
                    subject='FlatNetSite Hesap Doğrulama',
                    template='email/welcome',
                    user=new_user,
                    confirm_url=confirm_url # <-- DEĞİŞİKLİK BURADA: 'confirmation_link' yerine 'confirm_url' kullanılıyor
                )
            except Exception as e:
                current_app.logger.error(f"API Kayıt: Kullanıcıya aktivasyon e-postası gönderilemedi: {e}")
            # --- DÜZELTİLMİŞ KISIM SONU ---

            try:
                admins_to_notify = User.query.filter_by(apartment_id=new_user.apartment_id, role='admin').all()
                for admin in admins_to_notify:
                    send_email(
                        to=admin.email,
                        subject='Yeni Kullanıcı Kaydı Onayınızı Bekliyor',
                        template='email/new_user_for_approval',
                        admin_name=admin.name,
                        new_user=new_user,
                        approval_link=url_for('admin.pending_users', _external=True)
                    )
            except Exception as e:
                current_app.logger.error(f"API Kayıt: Yöneticiye onay e-postası gönderilemedi: {e}")

            user_data = {
                "id": new_user.id,
                "name": new_user.name,
                "email": new_user.email,
                "role": new_user.role,
                "apartment": {
                    "id": new_user.apartment.id,
                    "name": new_user.apartment.name
                },
                "block": {
                    "id": new_user.block.id,
                    "name": new_user.block.name
                } if new_user.block else None,
                "daire_no": new_user.daire_no,
                "phone_number": new_user.phone_number,
                "registration_date_string": new_user.created_at.strftime('%d.%m.%Y'),
                "is_waiting_for_approve": not new_user.is_active
            }

            return api_success(
                data=user_data,
                msg="Kaydınız alındı. E-posta hesabınıza gelen doğrulama linkine tıklayın. Sonra yöneticinizin onayını bekleyeceksiniz.",
                status_code=201
            )
        except Exception as e:
            current_app.logger.error(f"API Kayıt sırasında hata: {e}", exc_info=True)
            db.session.rollback()
            return api_error("Kayıt sırasında beklenmedik bir sunucu hatası oluştu.", 500)
    else:
        error_messages = [error for field, errors in form.errors.items() for error in errors]
        return api_error(", ".join(error_messages), 400)

@api_bp.route('/devices/register', methods=['POST'])
@jwt_required()
def register_device():
    """Push Bildirim Token'ını Kaydeder
    Mobil cihazın, push bildirimleri alabilmesi için gerekli olan token'ını
    (Google/iOS için FCM, Huawei için HMS) sunucuya kaydeder.
    Geçerli bir JWT (access_token) gereklidir.
    ---
    tags:
      - Push Bildirimleri (Push Notifications)
    security:
      - bearerAuth: []
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        description: "Kaydedilecek push token ve platform bilgisi."
        schema:
          id: PushTokenPayload
          required:
            - platform
            - token
          properties:
            platform:
              type: string
              description: "Cihazın platformu. 'android', 'ios' veya 'huawei' kabul edilir."
              enum: ["android", "ios", "huawei"]
            token:
              type: string
              description: "Cihaza ait push bildirim token'ı."
    responses:
      200:
        description: "Cihaz token'ı başarıyla kaydedildi."
      400:
        description: "Eksik JSON verisi veya 'platform'/'token' alanları eksik/geçersiz."
      401:
        description: Geçerli bir JWT (access_token) sağlanmadı.
      404:
        description: Token'a ait kullanıcı bulunamadı.
      500:
        description: Token kaydedilirken bir sunucu hatası oluştu.
    """
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    if not user:
        return api_error("Kullanıcı bulunamadı.", 404)

    data = request.get_json()
    if not data:
        return api_error("Eksik JSON verisi.", 400)

    # Dokümantasyona uygun olarak 'token' anahtarını öncelikli oku
    token = data.get('token') or data.get('fcm_token') or data.get('hms_token')
    platform = data.get('platform')

    service = None
    if platform in ['android', 'ios']:
        service = 'fcm'
    elif platform == 'huawei':
        service = 'hms'

    if token:
        token = token.strip()

    if not token:
        return api_error("JSON body içinde 'token' alanı zorunludur.", 400)
    
    if not service:
        platform_str = platform if platform is not None else "boş"
        return api_error(f"Geçersiz 'platform' değeri: '{platform_str}'. Sadece 'android', 'ios' veya 'huawei' kabul edilir.", 400)

    if len(token) > 512:
        return api_error("Geçersiz token formatı. Beklenenden çok uzun.", 400)

    try:

        # 1. Bu kullanıcı için bu token zaten var mı diye kontrol et.
        existing_token = PushToken.query.filter_by(user_id=user.id, token=token).first()

        # 2. Eğer bu kullanıcı için bu token zaten kayıtlı değilse, işlem yap.
        if not existing_token:
            # Önce bu kullanıcının diğer tüm eski token'larını temizle (cihaz değişikliği için)
            PushToken.query.filter_by(user_id=user.id).delete()

            # Şimdi yeni token'ı bu kullanıcı için ekle
            new_push_token = PushToken(
                user_id=user.id,
                token=token,
                service=service
            )
            db.session.add(new_push_token)
            db.session.commit()
            msg = f"Cihaz, {service.upper()} bildirimleri için başarıyla kaydedildi."
        else:
            msg = "Bu cihaz zaten bu kullanıcı için kayıtlı."
            
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Push token kaydedilirken hata oluştu: {e}")
        return api_error("Token kaydedilirken bir sunucu hatası oluştu.", 500)
    
    return api_success({"msg": msg})


@api_bp.route('/version-check', methods=['GET'])
def version_check():
    """Mobil Uygulama Versiyon Kontrolü
    Mobil uygulamanın başlangıçta çağıracağı bu endpoint, zorunlu ve en son
    uygulama versiyon bilgilerini döndürür. Bu sayede mobil uygulama, kullanıcıya
    zorunlu veya isteğe bağlı güncelleme uyarısı gösterebilir. Public'tir.
    ---
    tags:
      - Public & Helpers
    responses:
      200:
        description: Versiyon bilgileri başarıyla döndürüldü.
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
              properties:
                android:
                  type: object
                  properties:
                    mandatory_version:
                      type: string
                      example: "1.0.0"
                    latest_version:
                      type: string
                      example: "1.0.2"
                ios:
                  type: object
                  properties:
                    mandatory_version:
                      type: string
                      example: "1.0.0"
                    latest_version:
                      type: string
                      example: "1.0.2"
                update_message:
                  type: object
                  properties:
                    title:
                      type: string
                    body:
                      type: string
                    force_update_body:
                      type: string
    """
    android_mandatory_version = "1.0.0" 
    ios_mandatory_version = "1.0.0"
    
    android_latest_version = "1.0.2"
    ios_latest_version = "1.0.2"
    
    response_data = {
        "android": {
            "mandatory_version": android_mandatory_version,
            "latest_version": android_latest_version
        },
        "ios": {
            "mandatory_version": ios_mandatory_version,
            "latest_version": ios_latest_version
        },
        "update_message": {
            "title": "Yeni Güncelleme Mevcut",
            "body": "Uygulamanın yeni özelliklerinden faydalanmak ve daha stabil bir deneyim için lütfen en son sürüme güncelleyin.",
            "force_update_body": "Uygulamayı kullanmaya devam edebilmek için güncelleme yapmanız zorunludur. Lütfen App Store veya Google Play Store'dan en son sürümü indirin."
        }
    }
    
    return api_success(response_data)


@api_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    """Şifre Sıfırlama Talebi Başlatır
    Kullanıcının şifresini sıfırlayabilmesi için e-posta adresine özel bir link
    gönderilmesini tetikler. E-posta adresi sistemde kayıtlı olmasa bile,
    güvenlik nedeniyle her zaman başarılı mesajı döner. Public'tir.
    ---
    tags:
      - Kimlik Doğrulama (Authentication)
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          id: ForgotPasswordPayload
          required:
            - email
          properties:
            email:
              type: string
              format: email
              description: "Şifre sıfırlama linkinin gönderileceği e-posta adresi."
    responses:
      200:
        description: "İşlem başarıyla alındı. E-posta mevcutsa, sıfırlama linki gönderilir."
      400:
        description: "İstekte 'email' alanı eksik."
    """
    data = request.get_json()
    if not data or not data.get('email'):
        return api_error("E-posta adresi zorunludur.", 400)

    email = data.get('email').strip()
    user = User.query.filter_by(email=email).first()

    if user:
        try:
            token = user.get_reset_token()
            send_email(
                to=user.email,
                subject='Şifre Sıfırlama Talebi',
                template='email/reset_password',
                user=user,
                token=token
            )
        except Exception as e:
            current_app.logger.error(f"API - Şifre sıfırlama e-postası gönderilemedi: {e}")
    
    return api_success({
        "msg": "Eğer girdiğiniz e-posta adresi sistemimizde kayıtlı ise, şifre sıfırlama talimatları gönderilmiştir."
    })


@api_bp.route('/reset-password/<token>', methods=['POST'])
def reset_password(token):
    """Yeni Şifre Belirler
    E-posta ile gönderilen geçerli bir token ve yeni şifre ile kullanıcının
    şifresini günceller. Public'tir.
    ---
    tags:
      - Kimlik Doğrulama (Authentication)
    consumes:
      - application/json
    parameters:
      - name: token
        in: path
        type: string
        required: true
        description: "Kullanıcının e-postasına gönderilen şifre sıfırlama token'ı."
      - in: body
        name: body
        required: true
        schema:
          id: ResetPasswordPayload
          required:
            - password
            - confirm
          properties:
            password:
              type: string
              format: password
              description: "Kullanıcının yeni şifresi."
            confirm:
              type: string
              format: password
              description: "Yeni şifrenin onayı (aynı olmalıdır)."
    responses:
      200:
        description: "Şifre başarıyla güncellendi."
      400:
        description: "Token geçersiz/süresi dolmuş veya form validasyonu başarısız (örn: şifreler uyuşmuyor)."
    """
    user = User.verify_reset_token(token)
    if not user:
        return api_error("Geçersiz veya süresi dolmuş şifre sıfırlama linki.", 400)

    data = request.get_json()
    if not data:
        return api_error("Eksik JSON verisi", 400)

    form = ResetPasswordForm(data=data, csrf_enabled=False)

    if not form.validate():
        for field, errors in form.errors.items():
            error_message = f"{errors[0]}"
            return api_error(error_message, 400)
    
    hashed_password = generate_password_hash(form.password.data)
    user.password = hashed_password
    db.session.commit()

    return api_success({"msg": "Şifreniz başarıyla güncellendi. Şimdi giriş yapabilirsiniz."})

@api_bp.route('/profile/delete', methods=['POST'])
@jwt_required()
def api_delete_account():
    """Kullanıcı Hesabını Siler (Anonimleştirir)
    Giriş yapmış kullanıcının, mevcut şifresini doğrulayarak kendi hesabını
    kalıcı olarak anonimleştirmesini sağlar. Bu işlem geri alınamaz.
    Geçerli bir JWT (access_token) gereklidir.
    ---
    tags:
      - Profil (Profile)
    security:
      - bearerAuth: []
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          id: DeleteAccountPayload
          required:
            - password
          properties:
            password:
              type: string
              format: password
              description: "İşlemi onaylamak için kullanıcının mevcut şifresi."
    responses:
      200:
        description: "Hesap başarıyla silindi (anonimleştirildi)."
      400:
        description: "İstekte 'password' alanı eksik."
      401:
        description: "Geçerli bir JWT sağlanmadı veya girilen şifre yanlış."
      404:
        description: "Token'a ait kullanıcı bulunamadı."
      500:
        description: "İşlem sırasında bir sunucu hatası oluştu."
    """
    current_user_id = get_jwt_identity()
    user_to_delete = User.query.get(current_user_id)
    if not user_to_delete:
        return api_error("Kullanıcı bulunamadı.", 404)

    data = request.get_json()
    if not data or 'password' not in data:
        return api_error("İşlemi onaylamak için mevcut şifrenizi girmeniz zorunludur.", 400)

    password = data.get('password')

    if check_password_hash(user_to_delete.password, password):
        try:

            user_to_delete.name = f"{user_to_delete.name} (Hesap Kapatıldı)"

            unique_deleted_email = f"deleted_{user_to_delete.id}_{uuid.uuid4().hex[:8]}@deleted.com"
            user_to_delete.email = unique_deleted_email
            
            user_to_delete.phone_number = None

            user_to_delete.password = generate_password_hash(uuid.uuid4().hex)
            

            user_to_delete.is_active = False
            
            db.session.commit()
            
            return api_success(
                data={"msg": "Hesabınız başarıyla silinmiştir."},
                msg="Hesap silme işlemi başarılı."
            )
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"API - Hesap silinirken hata oluştu: {e}", exc_info=True)
            return api_error("Hesap silinirken beklenmedik bir sunucu hatası oluştu.", 500)
    else:
        return api_error("Girdiğiniz şifre yanlış.", 401)

@api_bp.route('/rules', methods=['GET'])
@jwt_required()
def get_rules():
    """Dinamik İçerikleri (Kurallar vb.) Getirir
    Yönetici panelinden eklenen/düzenlenen 'Site Kuralları', 'Havuz Kullanımı'
    gibi metin içeriklerini mobil uygulamada göstermek için listeler.
    İçerik, mobil tarafta düzgün görüntülenmesi için CSS class'larından
    arındırılmış temiz HTML olarak gönderilir.
    Geçerli bir JWT (access_token) gereklidir.
    ---
    tags:
      - Genel (General)
    security:
      - bearerAuth: []
    responses:
      200:
        description: "Dinamik içerik listesi başarıyla döndürüldü."
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: array
              items:
                type: object
                properties:
                  title:
                    type: string
                    example: "Site ve Apartman Genel Kuralları"
                  content:
                    type: string
                    example: "<h1>Başlık</h1><p>Bu bir kuraldır.</p>"
      401:
        description: Geçerli bir JWT (access_token) sağlanmadı.
      500:
        description: "İçerikler alınırken bir sunucu hatası oluştu."
    """
    try:
        contents = DynamicContent.query.all()
        
        rules_data = []
        for content in contents:
            raw_html = content.content
            soup = BeautifulSoup(raw_html, 'lxml')
            
            for tag in soup.find_all(attrs={'class': True}):
                del tag['class']

            cleaned_html = str(soup)
            
            rules_data.append({
                "title": content.title,
                "content": cleaned_html 
            })
        
        return api_success(rules_data)
        
    except Exception as e:
        current_app.logger.error(f"API - Kurallar çekilirken hata: {e}", exc_info=True)
        return api_error("Kurallar alınırken bir sunucu hatası oluştu.", 500)