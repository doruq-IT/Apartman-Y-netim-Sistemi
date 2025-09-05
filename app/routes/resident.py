import os
from flask import Blueprint, render_template, flash, request, redirect, url_for, current_app, jsonify, abort
from flask_login import login_required, current_user, login_user
from app.models import Announcement, Dues, User, db, Expense
from werkzeug.utils import secure_filename
from datetime import datetime, timezone, timedelta, time
from app.forms.receipt_form import ReceiptUploadForm
from app.models import Document, Announcement, Dues, User, db, CommonArea, Reservation, Transaction
from sqlalchemy import extract, func # YENİ: func (sum gibi fonksiyonlar için) eklendi
from app.models import Craftsman, CraftsmanRequestLog
from sqlalchemy.orm import joinedload
from app.forms.auth_forms import DeleteAccountForm
from werkzeug.security import check_password_hash, generate_password_hash
from app.gcs_utils import upload_to_gcs
from flask_login import logout_user
from app.forms.reservation_forms import ReservationForm
from app.document_ai_helper import process_receipt_from_gcs
from app.models import Request as RequestModel
import pytz
import uuid

resident_bp = Blueprint("resident", __name__)


@resident_bp.route("/dashboard")
@login_required
def dashboard():
    recent_announcements = Announcement.query.filter_by(
        apartment_id=current_user.apartment_id
    ).order_by(Announcement.created_at.desc()).limit(3).all()
    today = datetime.utcnow().date()
    
    # Güncel kasa bakiyesini hesapla
    total_balance = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.apartment_id == current_user.apartment_id
    ).scalar() or 0.0
    return render_template(
        "dashboard.html", 
        announcements=recent_announcements, 
        today=today,
        total_balance=total_balance  # <-- YENİ
    )


@resident_bp.route("/profile")
@login_required
def profile():
    user_documents = Document.query.filter_by(user_id=current_user.id).order_by(Document.upload_date.desc()).all()
    return render_template('profile.html', user=current_user, documents=user_documents)


@resident_bp.route("/dues")
@login_required
def dues_list():
    """Kullanıcının aidat listesini ve toplam borcunu gösterir. (Sayfalama Eklendi)"""

    # 1. URL'den sayfa numarasını al (?page=2 gibi). Varsayılan: 1. sayfa.
    page = request.args.get('page', 1, type=int)
    per_page = 10 # Sayfa başına gösterilecek aidat sayısı

    # 2. .all() yerine .paginate() kullanarak sadece ilgili sayfadaki aidatları çek.
    pagination = Dues.query.filter_by(user_id=current_user.id) \
        .order_by(Dues.due_date.desc()) \
        .paginate(page=page, per_page=per_page, error_out=False)
    
    # 3. Şablonda gösterilecek aidat listesini pagination nesnesinden al.
    dues_on_page = pagination.items

    # Toplam borç hesaplaması aynı kalıyor, çünkü bu tüm aidatları kapsamalı.
    total_debt_query = db.session.query(func.sum(Dues.amount)).filter(
        Dues.user_id == current_user.id,
        Dues.is_paid == False
    ).scalar()
    total_debt = total_debt_query or 0.0

    today = datetime.utcnow().date()
    
    # 4. Şablona hem o sayfadaki aidatları, hem de sayfa linkleri için pagination nesnesini gönder.
    return render_template("dues_list.html", 
                           dues=dues_on_page, 
                           today=today, 
                           total_debt=total_debt,
                           pagination=pagination) # <-- YENİ EKLENDİ


@resident_bp.route('/create_request')
@login_required
def create_request():
    return "<h3>Yeni talep oluşturma sayfası yakında gelecek.</h3>"


# YENİ upload_receipt FONKSİYONU
@resident_bp.route('/upload_receipt/<int:dues_id>', methods=['GET', 'POST'])
@login_required
def upload_receipt(dues_id):
    dues = Dues.query.get_or_404(dues_id)
    if dues.user_id != current_user.id:
        flash("Bu aidat size ait değil!", "danger")
        return redirect(url_for("resident.dues_list"))

    form = ReceiptUploadForm()
    if form.validate_on_submit():
        file_to_upload = form.file.data

        # 1. Dosyayı GCS'e yükle ve Document AI için GCS URI'ını al
        gcs_uri = upload_to_gcs(file_to_upload, 'receipts', return_gcs_uri=True)

        if not gcs_uri:
            flash("Makbuz yüklenirken bir sunucu hatası oluştu. Lütfen tekrar deneyin.", "danger")
            return redirect(url_for("resident.dues_list"))

        # 2. Document AI'a gönder ve verileri çıkar
        processor_id = current_app.config.get('DOCAI_PROCESSOR_ID')
        project_id = os.environ.get('GCLOUD_PROJECT') 
        location = current_app.config.get('DOCAI_LOCATION')

        extracted_data = process_receipt_from_gcs(gcs_uri, processor_id, project_id, location)

        # 3. Otomatik Onaylama Mantığı
        auto_approved = False
        if extracted_data and 'amount' in extracted_data:
            # Tutar kontrolü (1 TL'lik kuruş farklarına izin verelim)
            is_amount_ok = abs(extracted_data['amount'] - float(dues.amount)) < 1.0

            # Alıcı kontrolü (Apartman adının dekontta geçip geçmediği)
            supplier_name = extracted_data.get('supplier', '').lower()
            official_name_to_check = current_user.apartment.bank_account_name or current_user.apartment.name
            check_word = official_name_to_check.split()[0].lower()
            is_recipient_ok = check_word in supplier_name if supplier_name else False

            if is_amount_ok and is_recipient_ok:
                # BAŞARILI: Ödemeyi otomatik onayla
                dues.is_paid = True
                dues.payment_date = datetime.utcnow()
                dues.receipt_filename = gcs_uri

                income_transaction = Transaction(
                    amount=dues.amount,
                    description=f"Aidat Ödemesi (Otomatik Onay): {dues.user.name} - {dues.description}",
                    transaction_date=dues.payment_date,
                    source_type='dues', source_id=dues.id,
                    user_id=dues.user_id, apartment_id=dues.apartment_id
                )
                db.session.add(income_transaction)
                db.session.commit()
                flash("Dekontunuz otomatik olarak doğrulandı ve ödemeniz onaylandı!", "success")
                auto_approved = True

        if not auto_approved:
            # BAŞARISIZ veya VERİ ÇIKARILAMADI: Manuel onaya düşür
            dues.receipt_filename = gcs_uri
            dues.receipt_upload_date = datetime.utcnow()
            db.session.commit()
            flash("Dekontunuz yüklendi ve yönetici onayına gönderildi.", "info")

        return redirect(url_for("resident.dues_list"))

    return render_template("upload_receipt.html", form=form, dues=dues)

@resident_bp.route('/confirm-account-deletion/<token>')
def confirm_account_deletion(token):
    """
    E-posta ile gönderilen hesap silme token'ını doğrular.
    Token geçerliyse, kullanıcıyı sisteme giriş yaptırır ve
    son onay için şifre girme sayfasına yönlendirir.
    """
    user = User.verify_delete_token(token)

    if user is None:
        flash('Hesap silme linki geçersiz veya süresi dolmuş. Lütfen tekrar talepte bulunun.', 'warning')
        return redirect(url_for('public.request_account_deletion'))

    # Token geçerliyse, kullanıcıyı geçici olarak sisteme giriş yaptır
    login_user(user)

    flash('Hesabınızı kalıcı olarak silmek için lütfen son adım olarak şifrenizi girin.', 'info')
    # Kullanıcıyı, @login_required ile korunan mevcut şifre girme sayfasına yönlendir
    return redirect(url_for('resident.delete_account_request'))

@resident_bp.route('/delete-account', methods=['GET', 'POST'])
@login_required
def delete_account_request():
    """Kullanıcının hesabını silme isteğini yönetir."""
    form = DeleteAccountForm()
    
    if form.validate_on_submit():
        # 1. DÜZELTME: Şifre kontrolü artık Werkzeug ile yapılıyor.
        if check_password_hash(current_user.password, form.password.data):
            
            # 2. Şifre doğruysa, kullanıcıyı anonimleştir
            user_to_delete = current_user
            user_to_delete.name = f"{user_to_delete.name} (Hesap Kapatıldı)"
            
            unique_deleted_email = f"deleted_{user_to_delete.id}_{uuid.uuid4().hex[:8]}@deleted.com"
            user_to_delete.email = unique_deleted_email
            
            user_to_delete.phone_number = None
            # 3. DÜZELTME: Yeni şifre de Werkzeug ile oluşturuluyor.
            user_to_delete.password = generate_password_hash(uuid.uuid4().hex)
            
            # Hesabı pasif hale getir
            user_to_delete.is_active = False
            
            db.session.commit()
            
            logout_user()
            
            flash('Hesabınız başarıyla silinmiştir. Sizi tekrar aramızda görmeyi umuyoruz.', 'success')
            return redirect(url_for('public.index'))
        else:
            flash('Girdiğiniz şifre yanlış. Lütfen tekrar deneyin.', 'danger')
            return redirect(url_for('resident.delete_account_request'))

    return render_template('delete_account_form.html', form=form)

@resident_bp.route("/reservation/areas")
@login_required
def list_reservation_areas():
    """
    Sakinin kendi apartmanındaki rezervasyona açık olan tüm ortak
    alanları listeler.
    """
    # Sadece 'aktif' olan ortak alanları veritabanından çek.
    areas = CommonArea.query.filter_by(
        apartment_id=current_user.apartment_id,
        is_active=True
    ).order_by(CommonArea.name).all()

    return render_template("resident/area_list.html",
                           title="Ortak Alanlar ve Rezervasyon",
                           areas=areas)

@resident_bp.route("/api/reservations/<int:area_id>")
@login_required
def get_reservations_for_area(area_id):
    """
    Belirli bir ortak alana ait tüm rezervasyonları FullCalendar'ın anlayacağı
    JSON formatında döndürür. (Daha Güçlü Versiyon)
    """
    try:
        reservations = Reservation.query.filter_by(common_area_id=area_id).all()

        events = []
        for reservation in reservations:
            # Rezervasyonu yapan kullanıcı silinmiş veya bulunamıyor olabilir.
            # Bu durumu kontrol ederek hatayı önleyelim.
            reserver_name = "Bilinmeyen"
            if reservation.user:
                reserver_name = reservation.user.name.split()[0]

            events.append({
                'title': f"Dolu ({reserver_name})",
                # Saatin UTC olduğunu belirtmek için sonuna 'Z' ekliyoruz.
                'start': reservation.start_time.isoformat() + 'Z',
                'end': reservation.end_time.isoformat() + 'Z',
                'color': '#6c757d' 
            })
        return jsonify(events)
    except Exception as e:
        # Bir hata oluşursa, sunucu loglarına yazdır ve takvimin bozulmaması
        # için boş bir liste döndür.
        current_app.logger.error(f"Rezervasyonlar çekilirken hata oluştu (Alan ID: {area_id}): {e}")
        return jsonify([])


@resident_bp.route("/reservation/area/<int:area_id>")
@login_required
def reservation_calendar(area_id):
    """Belirli bir ortak alan için rezervasyon takvimini gösteren sayfayı render eder."""
    area = CommonArea.query.get_or_404(area_id)
    if area.apartment_id != current_user.apartment_id:
        abort(403) # Başka apartmanın takvimini göremez.

    return render_template("resident/reservation_calendar.html", 
                           title=f"{area.name} - Rezervasyon Takvimi", 
                           area=area)

@resident_bp.route("/reservation/area/<int:area_id>/new", methods=['GET', 'POST'])
@login_required
def create_reservation(area_id):
    """Yeni bir rezervasyon oluşturma sayfasını yönetir (Süre, Kapasite ve KESİN Zaman Dilimi Kontrollü)."""
    form = ReservationForm()
    area = CommonArea.query.get_or_404(area_id)

    if form.validate_on_submit():
        start_time_str = request.form.get('start_time')
        num_of_people_requested = form.num_of_people.data
        duration_hours = form.duration.data

        try:
            # 1. Gelen "saf" (naive) yerel saat metnini bir datetime nesnesine çevir.
            naive_start_time = datetime.fromisoformat(start_time_str)
        except ValueError:
            flash("Geçersiz tarih formatı. Lütfen tekrar deneyin.", "danger")
            return redirect(url_for('resident.reservation_calendar', area_id=area_id))

        # 2. KESİN ÇÖZÜM: Saatin Türkiye saat dilimine ait olduğunu AÇIKÇA belirt.
        local_tz = pytz.timezone('Europe/Istanbul')
        aware_start_time = local_tz.localize(naive_start_time)

        # 3. Artık "farkında" olan yerel saati EVRENSEL SAAT'e (UTC) çevir.
        utc_start_time = aware_start_time.astimezone(pytz.utc)
        
        # 4. Bitiş saatini UTC başlangıç saatine göre hesapla.
        utc_end_time = utc_start_time + timedelta(hours=duration_hours)

        # === VALIDASYON KONTROLLERİ (Bu kısım zaten doğru çalışıyor) ===
        overlapping_reservations = Reservation.query.filter(
            Reservation.common_area_id == area_id,
            Reservation.start_time < utc_end_time,
            Reservation.end_time > utc_start_time
        ).all()
        # ... (geri kalan validasyon kodları aynı kalacak) ...
        current_occupancy = sum(res.num_of_people for res in overlapping_reservations)
        total_requested_occupancy = current_occupancy + num_of_people_requested

        if total_requested_occupancy > area.capacity:
            remaining_capacity = area.capacity - current_occupancy
            flash(f"Seçtiğiniz zaman aralığı için yeterli kapasite yok. Kalan kapasite: {remaining_capacity if remaining_capacity > 0 else 0} kişi.", "danger")
            return redirect(url_for('resident.reservation_calendar', area_id=area_id))
        
        if utc_start_time < datetime.now(timezone.utc):
            flash("Geçmiş bir tarihe rezervasyon yapamazsınız.", "danger")
            return redirect(url_for('resident.reservation_calendar', area_id=area_id))
        
        # === REZERVASYONU OLUŞTURMA (Veritabanına UTC olarak kaydediyoruz) ===
        new_reservation = Reservation(
            start_time=utc_start_time,
            end_time=utc_end_time,
            notes=form.notes.data,
            num_of_people=num_of_people_requested,
            user_id=current_user.id,
            common_area_id=area.id,
            apartment_id=current_user.apartment_id
        )
        db.session.add(new_reservation)
        db.session.commit()

        flash("Rezervasyonunuz başarıyla oluşturuldu!", "success")
        return redirect(url_for('resident.reservation_calendar', area_id=area_id))

    # GET isteği için olan kısım aynı kalıyor.
    start_time_str = request.args.get('start')
    try:
        start_dt = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
        end_dt = start_dt + timedelta(hours=1)
        end_time_str = end_dt.isoformat()
    except (ValueError, TypeError):
        end_time_str = ""
    
    return render_template("resident/create_reservation.html",
                           title="Rezervasyonu Onayla",
                           area=area,
                           form=form,
                           start_time=start_time_str,
                           end_time=end_time_str)

# =================================================================
# YENİ: Sakinler için Usta Rehberi Sayfası
# =================================================================
@resident_bp.route("/craftsmen")
@login_required
def view_craftsmen():
    """
    Sakinin, kendi apartmanına kayıtlı olan tüm ustaları görmesini sağlar.
    """
    # 1. Sakinin apartmanına ait olan tüm ustaları veritabanından çek.
    #    Uzmanlık alanına göre alfabetik olarak sırala.
    craftsmen_list = Craftsman.query.filter_by(
        apartment_id=current_user.apartment_id
    ).order_by(Craftsman.specialty).all()

    # 2. Çektiğin usta listesini, birazdan oluşturacağımız şablona gönder.
    return render_template("resident/craftsmen_list.html",
                           title="Anlaşmalı Usta Rehberi",
                           craftsmen=craftsmen_list)

# ===== YENİ AYLIK FİNANSAL ÖZET SAYFASI =====
@resident_bp.route("/monthly_summary")
@login_required
def monthly_summary():
    """Sakinler için mevcut ayın gelir ve giderlerini gösteren sayfa."""
    
    today = datetime.utcnow()
    start_of_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    # Ay sonunu doğru hesaplamak için (tüm aylarda çalışır)
    next_month = start_of_month.replace(day=28) + timedelta(days=4)
    end_of_month = next_month - timedelta(days=next_month.day)
    end_of_month = end_of_month.replace(hour=23, minute=59, second=59)

    # --- YENİ GİDER SORGULAMA MANTIĞI ---
    # Transaction ve Expense tablolarını birleştirerek giderleri sorgula
    expense_results = db.session.query(
        Transaction, Expense.invoice_filename
    ).outerjoin(
        Expense, db.and_(
            Transaction.source_type == 'expense',
            Transaction.source_id == Expense.id
        )
    ).filter(
        Transaction.apartment_id == current_user.apartment_id,
        Transaction.transaction_date.between(start_of_month, end_of_month),
        Transaction.amount < 0
    ).order_by(Transaction.transaction_date.desc()).all()

    # Şablonda daha kolay kullanmak için veriyi yeniden yapılandır
    monthly_expense_list = []
    for transaction, invoice_filename in expense_results:
        monthly_expense_list.append({
            'transaction': transaction,
            'invoice_filename': invoice_filename
        })
    
    total_monthly_expense = sum(item['transaction'].amount for item in monthly_expense_list)
    # --- GİDER SORGULAMA BİTİŞİ ---

    # --- GELİR SORGULAMA KISMI AYNI KALIYOR ---
    income_transactions = Transaction.query.filter(
        Transaction.apartment_id == current_user.apartment_id,
        Transaction.transaction_date.between(start_of_month, end_of_month),
        Transaction.amount > 0
    ).all()
    
    total_monthly_income = sum(t.amount for t in income_transactions)
    
    income_summary = {}
    for trans in income_transactions:
        description_key = "Aidat Gelirleri" if "Aidat" in trans.description else trans.description
        if description_key not in income_summary:
            income_summary[description_key] = 0
        income_summary[description_key] += trans.amount
    
    income_summary_list = [{'description': desc, 'amount': total} for desc, total in income_summary.items()]
    # --- GELİR KISMI BİTİŞİ ---

    return render_template(
        "resident/monthly_summary.html",
        title="Bu Ayın Finansal Özeti",
        current_month_name=start_of_month.strftime('%B %Y'),
        income_list=income_summary_list,
        expense_list=monthly_expense_list, # <-- Artık fatura bilgisini de içeren listeyi gönderiyoruz
        total_income=total_monthly_income,
        total_expense=total_monthly_expense
    )
# ===== YENİ FONKSİYON BİTİŞİ =====
@resident_bp.route('/requests/<int:request_id>', methods=['GET'])
@login_required
def view_request(request_id):
    req = RequestModel.query.get_or_404(request_id)

    # Yetki: kendi talebi ya da (aynı apartmandan) admin/superadmin görebilsin
    if req.user_id != current_user.id:
        if current_user.role not in ('admin', 'superadmin'):
            abort(403)
        if current_user.role == 'admin' and req.apartment_id != current_user.apartment_id:
            abort(403)

    return render_template('requests/view_request.html', req=req)

@resident_bp.route('/craftsmen/<int:craftsman_id>/request', methods=['POST'])
@login_required # <-- JWT yerine normal session çerezi ile koruma
def request_craftsman_contact_web(craftsman_id):
    """
    WEB SİTESİNDEKİ JavaScript tarafından çağrılmak üzere tasarlanmıştır.
    Bir usta için iletişim talebini kaydeder ve telefon numarasını döndürür.
    """
    user = current_user
    craftsman = Craftsman.query.get_or_404(craftsman_id)

    # Güvenlik Kontrolü
    if craftsman.apartment_id != user.apartment_id:
        return jsonify({"success": False, "errorMessage": "Bu ustaya erişim yetkiniz yok."}), 403

    # Veritabanına log kaydını oluştur (API'deki ile aynı mantık)
    try:
        log_entry = CraftsmanRequestLog(
            resident_id=user.id,
            craftsman_id=craftsman.id,
            apartment_id=user.apartment_id
        )
        db.session.add(log_entry)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Usta talep logu (WEB) kaydedilirken hata: {e}")
        return jsonify({"success": False, "errorMessage": "Sunucu hatası oluştu."}), 500

    # Başarılı yanıtta ustanın telefon numarasını JSON formatında döndür
    return jsonify({
        "success": True,
        "msg": "Talep oluşturuldu. Usta ile iletişime geçebilirsiniz.",
        "data": {
            "phone_number": craftsman.phone_number
        }
    })
