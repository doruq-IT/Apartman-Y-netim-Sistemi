from flask_login import current_user
from .models import Request, RequestStatus, Dues, User, Announcement
from datetime import datetime

def inject_counts():
    """
    Giriş yapmış kullanıcının rolüne göre, menülerde gösterilecek sayaçları hesaplar
    ve tüm şablonların kullanımına sunar.
    """
    counts = {
        'pending_requests_count': 0,
        'pending_receipts_count': 0,
        'unpaid_dues_count': 0,
        'total_admin_notifications': 0,
        'pending_users_count': 0,
        'unread_announcements_count': 0, # <-- YENİ SAYAÇ EKLENDİ
        'current_year': datetime.utcnow().year
    }

    if current_user.is_authenticated:
        if current_user.role in ['admin', 'superadmin']:
            # Mevcut sayaçlar (değişiklik yok)
            counts['pending_requests_count'] = Request.query.filter_by(apartment_id=current_user.apartment_id, status=RequestStatus.BEKLEMEDE).count()
            counts['pending_receipts_count'] = Dues.query.filter_by(apartment_id=current_user.apartment_id, is_paid=False).filter(Dues.receipt_filename.isnot(None)).count()
            counts['pending_users_count'] = User.query.filter_by(apartment_id=current_user.apartment_id, is_active=False).count()
            counts['total_admin_notifications'] = counts['pending_requests_count'] + counts['pending_receipts_count'] + counts['pending_users_count']
        
        if current_user.role == 'resident':
            # Mevcut aidat sayacı (değişiklik yok)
            counts['unpaid_dues_count'] = Dues.query.filter_by(user_id=current_user.id, is_paid=False).count()

            # --- YENİ EKLENEN OKUNMAMIŞ DUYURU SAYACI MANTIĞI ---
            # 1. Kullanıcının apartmanındaki toplam duyuru sayısını bul
            total_announcements_count = Announcement.query.filter_by(apartment_id=current_user.apartment_id).count()
            
            # 2. Kullanıcının okuduğu duyuruların sayısını bul
            read_announcements_count = current_user.read_announcements.count()
            
            # 3. Aradaki fark, okunmamış duyuru sayısını verir
            counts['unread_announcements_count'] = total_announcements_count - read_announcements_count
            # --- YENİ MANTIĞIN SONU ---
    
    return counts