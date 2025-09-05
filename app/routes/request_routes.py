from flask import Blueprint, render_template, redirect, url_for, flash, current_app, request
from flask_login import login_required, current_user
from app.forms.request_form import RequestForm
# YENİ: User ve RequestStatus modellerini de import ediyoruz.
from app.models import db, User, Request as RequestModel, RequestStatus
# YENİ: E-posta gönderme fonksiyonumuzu import ediyoruz.
from app.email import send_email
from app.gcs_utils import upload_to_gcs
from datetime import datetime
import pytz


# Blueprint tanımı
request_bp = Blueprint('resident_request', __name__)

# Talep listeleme
@request_bp.route('/requests', methods=['GET'])
@login_required
def request_list():
    # 1. URL'den sayfa numarasını al (?page=2 gibi). Varsayılan: 1. sayfa.
    page = request.args.get('page', 1, type=int)
    per_page = 10 # Sayfa başına gösterilecek talep sayısı

    # 2. .all() yerine .paginate() kullanarak sadece ilgili sayfadaki talepleri çek.
    pagination = RequestModel.query \
        .filter_by(user_id=current_user.id) \
        .order_by(RequestModel.created_at.desc()) \
        .paginate(page=page, per_page=per_page, error_out=False)

    # 3. Şablonda gösterilecek talep listesini pagination nesnesinden al.
    user_requests = pagination.items

    # 4. Şablona hem talepleri, hem de sayfa linkleri için pagination nesnesini gönder.
    return render_template('requests/request_list.html', 
                           requests=user_requests,
                           pagination=pagination) # <-- YENİ EKLENDİ

# Talep oluşturma
@request_bp.route('/requests/create', methods=['GET', 'POST'])
@login_required
def create_request():
    form = RequestForm()

    if form.validate_on_submit():
        if not current_user.apartment_id:
            flash("Apartman bilgisi bulunamadı. Lütfen yöneticiyle iletişime geçin.", "danger")
            return redirect(url_for("resident_request.request_list"))

        # --- Seçeneklerin görünen etiketlerini bulalım (DB'ye okunur yazalım) ---
        def get_label(field, value):
            # WTForms SelectField: choices -> list of (value, label)
            return dict(field.choices).get(value, value)

        category_label = get_label(form.category, form.category.data)    # Arıza / Bakım / Yeni talep / Diğer
        priority_label = get_label(form.priority, form.priority.data)    # Düşük / Orta / Yüksek

        # Konum: 'Diğer' ise serbest metni al, değilse seçili etiket
        if form.location.data == "diger":
            location_value = (form.location_other.data or "").strip()
        else:
            location_value = get_label(form.location, form.location.data)

        # --- Dosya (opsiyonel) ---
        attachment_url = None
        file_storage = form.attachment.data  # FileField -> werkzeug FileStorage veya None
        if file_storage and getattr(file_storage, "filename", ""):
            # GCS'e yükle: klasör adı 'requests' (istersen değiştir)
            uploaded = upload_to_gcs(file_storage, 'requests')
            if not uploaded:
                flash("Dosya yüklenirken bir sorun oluştu. Lütfen tekrar deneyin.", "danger")
                return redirect(url_for("resident_request.create_request"))
            attachment_url = uploaded  # Tam URL döndürüyor (GCS public url)

        # --- Yeni talebi oluştur ---
        new_request = RequestModel(
            title=form.title.data.strip(),
            description=form.description.data.strip(),
            user_id=current_user.id,
            apartment_id=current_user.apartment_id,
            status=RequestStatus.BEKLEMEDE,

            # Yeni alanlar:
            category=category_label,
            priority=priority_label,
            location=location_value,
            attachment_url=attachment_url
        )
        db.session.add(new_request)
        db.session.commit()

        # --- Yöneticiyi e-posta ile bilgilendir (mevcut mantık + ekstra parametreler) ---
        try:
            admin = User.query.filter_by(
                apartment_id=current_user.apartment_id,
                role='admin'
            ).first()

            if admin and admin.email:
                send_email(
                    to=admin.email,
                    subject=f"Yeni Talep Bildirimi: {new_request.title}",
                    template='email/new_request_to_admin',
                    resident_name=current_user.name,
                    request_title=new_request.title,
                    request_id=new_request.id,
                    # ekstra bilgi (şablon kullanırsa)
                    category=new_request.category,
                    priority=new_request.priority,
                    location=new_request.location,
                    attachment_url=new_request.attachment_url
                )
        except Exception as e:
            current_app.logger.error(f"Yöneticiye yeni talep e-postası gönderilemedi: {e}")

        flash('Talebiniz başarıyla oluşturuldu.', 'success')
        return redirect(url_for('resident_request.request_list'))

    return render_template('requests/create_request.html', form=form)

# Talep detayı (sadece sahibi görebilsin)
# app/routes/request_routes.py

@request_bp.route('/requests/<int:request_id>', methods=['GET'])
@login_required
def view_request(request_id):
    req = RequestModel.query.filter_by(id=request_id, user_id=current_user.id).first_or_404()

    # === YENİ EKLENEN ZAMAN ÇEVİRME BÖLÜMÜ ===
    local_tz = pytz.timezone('Europe/Istanbul')
    
    if req.created_at:
        req.created_at = req.created_at.replace(tzinfo=pytz.utc).astimezone(local_tz)
    
    if req.updated_at:
        req.updated_at = req.updated_at.replace(tzinfo=pytz.utc).astimezone(local_tz)
    # === YENİ BÖLÜMÜN SONU ===

    return render_template('requests/view_request.html', req=req)

