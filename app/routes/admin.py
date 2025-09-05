from flask import Blueprint, render_template, flash, redirect, url_for, request, current_app, abort
from app.forms.announcement_form import AnnouncementForm
from app.models import Announcement, RequestStatus, Dues, User, Expense, Transaction, Document
from flask_login import login_required, current_user
from app.models import Request as RequestModel, db
from app.forms.request_reply_form import RequestReplyForm
from app.forms.dues_forms import DuesForm
from datetime import datetime, time
from app.forms.poll_forms import PollCreateForm
from app.models import Poll, PollOption, Vote
from app.email import send_email
from app.forms.admin_forms import CSRFProtectForm, UpdateRequestStatusForm, ExpenseForm, ManualTransactionForm, FinancialReportForm
from dateutil.relativedelta import relativedelta
from app.forms.admin_forms import CraftsmanForm
from app.notifications import send_push_notification, send_notification_to_users
from app.models import DynamicContent
from app.forms.admin_forms import DynamicContentForm
from app.models import Craftsman
from app.models import Block
from sqlalchemy import or_
from app.extensions import db
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from werkzeug.utils import secure_filename
from functools import wraps
from app.forms.reservation_forms import CommonAreaForm
from app.models import CommonArea
from app.gcs_utils import upload_to_gcs
from app.forms.blog_forms import PostForm
from app.models import Post
import os
import uuid
from app.forms.admin_forms import RecurringExpenseForm 
from app.models import RecurringExpense

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            abort(403)  # Forbidden (Erişim Engellendi)
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route("/dashboard")
@login_required
@admin_required
def dashboard():
    stats = {}
    apartment_id = current_user.apartment_id

    # Mevcut istatistikleriniz aynı kalıyor
    stats['pending_requests'] = RequestModel.query.filter_by(apartment_id=apartment_id, status=RequestStatus.BEKLEMEDE).count()
    stats['total_residents'] = User.query.filter_by(apartment_id=apartment_id, role='resident').count()
    stats['pending_receipts'] = Dues.query.filter(
        Dues.apartment_id == apartment_id,
        Dues.is_paid == False,
        Dues.receipt_filename.isnot(None)
    ).count()

    # --- YENİ GÜNCEL KASA BAKİYESİ HESAPLAMASI ---
    # Eski 'monthly_income' sorgusu kaldırıldı.
    # Transaction tablosundaki tüm gelir ve giderlerin toplamı alınarak net bakiye hesaplanıyor.
    total_balance_query = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.apartment_id == apartment_id
    ).scalar()
    stats['total_balance'] = total_balance_query or 0.0
    # --- HESAPLAMA BİTİŞİ ---

    # Son 5 talep ve grafik verileri için olan kodlarınız aynı kalıyor
    recent_requests = RequestModel.query.filter_by(apartment_id=apartment_id).order_by(RequestModel.created_at.desc()).limit(5).all()

    chart_labels = []
    income_data = []
    expense_data = []
    today = datetime.utcnow()

    for i in range(6):
        month_date = today - relativedelta(months=i)
        start_of_month = month_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_of_month = (start_of_month + relativedelta(months=1))

        chart_labels.append(start_of_month.strftime('%B'))

        monthly_income = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.apartment_id == apartment_id,
            Transaction.amount > 0,
            Transaction.transaction_date >= start_of_month,
            Transaction.transaction_date < end_of_month
        ).scalar() or 0
        income_data.append(monthly_income)

        monthly_expense = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.apartment_id == apartment_id,
            Transaction.amount < 0,
            Transaction.transaction_date >= start_of_month,
            Transaction.transaction_date < end_of_month
        ).scalar() or 0
        expense_data.append(abs(monthly_expense))

    chart_labels.reverse()
    income_data.reverse()
    expense_data.reverse()
    
    chart_data = {
        'labels': chart_labels,
        'income': income_data,
        'expenses': expense_data
    }

    return render_template(
        "admin_dashboard.html", 
        user=current_user, 
        recent_requests=recent_requests, 
        stats=stats,
        chart_data=chart_data
    )

# YENİ financial_report FONKSİYONU
@admin_bp.route('/reports/financial', methods=['GET', 'POST'])
@login_required
@admin_required
def financial_report():
    form = FinancialReportForm()
    
    if not form.validate_on_submit():
        return render_template('admin/financial_report_form.html', form=form, title="Finansal Rapor Oluştur")

    start_date_form = form.start_date.data
    end_date_form = form.end_date.data
    start_date = datetime.combine(start_date_form, time.min)
    end_date = datetime.combine(end_date_form, time.max)
    apartment_id = current_user.apartment_id

    # 1. Başlangıç bakiyesini ve tüm işlemleri çek (Bu kısımlar aynı)
    starting_balance = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.apartment_id == apartment_id,
        Transaction.transaction_date < start_date
    ).scalar() or 0.0

    transactions_from_db = Transaction.query.filter(
        Transaction.apartment_id == apartment_id,
        Transaction.transaction_date.between(start_date, end_date)
    ).order_by(Transaction.transaction_date.asc()).all()

    # 2. Rapor satırlarını ve GRAFİK VERİLERİNİ işlemek için hazırlık yap
    total_dues_income = 0
    other_transactions = []
    expense_chart_data = {} # Pasta grafik için giderleri toplayacağımız sözlük

    # 3. Tüm işlemleri döngüye alarak grupla
    for t in transactions_from_db:
        if t.source_type == 'dues' and t.amount > 0:
            total_dues_income += t.amount
        else:
            other_transactions.append(t)
            # Eğer işlem bir gider ise, grafik verisi için ayrıca grupla
            if t.amount < 0:
                # Giderin açıklamasını anahtar olarak kullan
                description_key = t.description
                if description_key not in expense_chart_data:
                    expense_chart_data[description_key] = 0
                # Giderleri pozitif olarak topla
                expense_chart_data[description_key] += abs(t.amount)

    report_lines = other_transactions
    if total_dues_income > 0:
        dues_summary_transaction = Transaction(
            description="Toplam Aidat Gelirleri",
            amount=total_dues_income,
            transaction_date=start_date
        )
        report_lines.insert(0, dues_summary_transaction)
    
    # 4. YENİ: Grafik verisini Chart.js'in anlayacağı formata çevir
    chart_labels = list(expense_chart_data.keys())
    chart_values = list(expense_chart_data.values())
    
    chart_data = {
        "labels": chart_labels,
        "values": chart_values
    }

    # 5. Özet hesaplamaları yap (Aynı)
    total_income = sum(t.amount for t in report_lines if t.amount > 0)
    total_expense = sum(t.amount for t in report_lines if t.amount < 0)
    ending_balance = starting_balance + total_income + total_expense
    
    # 6. Tüm verileri (rapor satırları + YENİ grafik verisi) şablona gönder
    return render_template(
        "admin/financial_report_template.html",
        start_date=start_date_form,
        end_date=end_date_form,
        starting_balance=starting_balance,
        transactions=report_lines,
        total_income=total_income,
        total_expense=abs(total_expense),
        ending_balance=ending_balance,
        apartment_name=current_user.apartment.name,
        generation_date=datetime.utcnow(),
        chart_data=chart_data  # <-- YENİ EKLENEN GRAFİK VERİSİ
    )
@admin_bp.route("/residents")
@login_required
@admin_required
def list_residents():
    """
    Yöneticinin kendi apartmanındaki tüm sakinleri listeler.
    Arama ve filtreleme özelliklerini içerir.
    """
    # 1. Yöneticinin apartman ID'sini ve arama parametrelerini al.
    admin_apartment_id = current_user.apartment_id
    search_query = request.args.get('search_query', '').strip()
    block_filter = request.args.get('block_filter', '')

    # 2. Temel veritabanı sorgusunu oluştur (sadece yöneticinin apartmanındaki sakinler).
    base_query = User.query.filter_by(
        apartment_id=admin_apartment_id, 
        role='resident'
    )

    # 3. Gelen parametrelere göre sorguyu dinamik olarak daha da filtrele.
    if search_query:
        search_term = f"%{search_query}%"
        base_query = base_query.filter(or_(User.name.ilike(search_term), User.email.ilike(search_term)))

    if block_filter:
        base_query = base_query.filter(User.block_id == int(block_filter))

    # 4. Sonuçları isme göre sırala ve tümünü çek.
    residents = base_query.order_by(User.name).all()
    
    # 5. Filtre dropdown menüsünü doldurmak için bu apartmana ait blokları çek.
    blocks_for_filter = Block.query.filter_by(apartment_id=admin_apartment_id).order_by(Block.name).all()

    # 6. Arama parametrelerini, formda seçili kalmaları için şablona geri gönder.
    search_args = request.args.to_dict()
    
    return render_template(
        "admin/resident_list.html", 
        residents=residents, 
        title="Apartman Sakinleri",
        blocks=blocks_for_filter,      # <-- YENİ EKLENDİ
        search_args=search_args        # <-- YENİ EKLENDİ
    )

@admin_bp.route("/resident/<int:user_id>/details")
@login_required
@admin_required
def view_resident_details(user_id):
    """
    Belirli bir sakinin detaylarını ve yüklediği belgeleri gösterir.
    """
    # 1. URL'den gelen ID ile sakini veritabanından bul. Bulamazsan 404 hatası ver.
    resident = User.query.get_or_404(user_id)

    # 2. GÜVENLİK KONTROLÜ: Yönetici, başka bir apartmandaki bir sakinin
    #    bilgilerine erişmeye çalışıyor mu? Engelle.
    if resident.apartment_id != current_user.apartment_id or resident.role != 'resident':
        abort(403) # Erişim Engellendi

    # 3. Bu sakine ait tüm belgeleri, en yeniden eskiye doğru sıralayarak çek.
    documents = Document.query.filter_by(user_id=resident.id).order_by(Document.upload_date.desc()).all()

    # 4. Hem sakinin bilgilerini hem de belge listesini şablona gönder.
    return render_template("admin/resident_detail.html", resident=resident, documents=documents)

@admin_bp.route('/expenses/add', methods=['GET', 'POST'])
@login_required
def add_expense():
    if current_user.role != 'admin':
        flash("Bu sayfaya erişim yetkiniz yok.", 'danger')
        return redirect(url_for('resident.dashboard'))
    
    # Eğer kullanıcı bir apartmana bağlı değilse hata ver ve geri dön
    if not current_user.apartment_id:
        flash("Apartman bilgisi eksik, işlem yapılamadı.", "danger")
        return redirect(url_for("admin.dashboard"))

    form = ExpenseForm()
    if form.validate_on_submit():
        invoice_file_name = None
        if form.invoice.data:
            uploaded_file = form.invoice.data
            # Dosyayı sunucuya değil, GCS'e 'invoices' klasörüne yükle
            invoice_url = upload_to_gcs(uploaded_file, 'invoices')
            if not invoice_url:
                flash("Fatura dosyası yüklenirken bir hata oluştu.", "danger")
                return redirect(url_for('admin.add_expense'))
            invoice_file_name = invoice_url # Veritabanına dosyanın GCS URL'ini kaydet

        # 💡 apartment_id eklendi!
        new_expense = Expense(
            apartment_id=current_user.apartment_id,
            description=form.description.data,
            amount=form.amount.data,
            expense_date=form.expense_date.data,
            invoice_filename=invoice_file_name,
            created_by_id=current_user.id
        )
        db.session.add(new_expense)
        db.session.flush()  # new_expense.id kullanılabilsin diye

        expense_transaction = Transaction(
            amount=-new_expense.amount,
            description=f"Masraf: {new_expense.description}",
            transaction_date=datetime.utcnow(),
            source_type='expense',
            source_id=new_expense.id,
            user_id=current_user.id,
            apartment_id=current_user.apartment_id
        )
        db.session.add(expense_transaction)

        db.session.commit()

        flash('Masraf ve ilgili kasa işlemi başarıyla kaydedildi.', 'success')
        return redirect(url_for('admin.dashboard'))

    return render_template('admin/add_expense.html', form=form)


# ... (Diğer fonksiyonlarınız...)
@admin_bp.route("/dues/add", methods=["GET", "POST"])
@login_required
@admin_required
def add_dues():
    form = DuesForm()
    # Dropdown menüsünü yöneticinin kendi apartmanındaki sakinlerle doldur
    form.user_id.choices = [
        (user.id, user.name) for user in User.query.filter_by(
            apartment_id=current_user.apartment_id, 
            role='resident'
        ).order_by(User.name).all()
    ]
    form.user_id.choices.insert(0, (0, '--- Sakin Seçin ---'))

    if form.validate_on_submit():
        # --- SENARYO 1: TÜM SAKİNLERE AİDAT ATA (Optimize Edilmiş) ---
        if form.assign_to_all.data:
            residents = User.query.filter_by(
                apartment_id=current_user.apartment_id,
                role='resident',
                is_active=True # Sadece aktif sakinlere gönderelim
            ).all()
            
            # 1. Adım: Aidat borçlarını ve e-postaları döngü içinde oluştur
            for resident in residents:
                # Bu aidat bu kullanıcı için daha önce oluşturulmuş mu diye kontrol et
                existing_due = Dues.query.filter_by(user_id=resident.id, description=form.description.data).first()
                if not existing_due:
                    new_due = Dues(
                        user_id=resident.id,
                        amount=form.amount.data,
                        description=form.description.data,
                        due_date=form.due_date.data,
                        apartment_id=resident.apartment_id
                    )
                    db.session.add(new_due)
                    
                    # E-posta bildirimi gönder (e-posta tek tek gitmek zorunda)
                    try:
                        send_email(
                            to=resident.email,
                            subject=f"Yeni Aidat Bildirimi: {new_due.description}",
                            template='email/new_dues_notification',
                            resident_name=resident.name,
                            dues=new_due
                        )
                    except Exception as e:
                        current_app.logger.error(f"Aidat e-postası gönderilemedi (Kullanıcı: {resident.id}): {e}")

            # 2. Adım: Oluşturulan tüm aidatları veritabanına kaydet
            db.session.commit()

            # 3. Adım: Döngü bittikten sonra TEK SEFERDE toplu push bildirimi gönder
            if residents:
                try:
                    send_notification_to_users(
                        users=residents,
                        title="Yeni Aidat Borcu",
                        body=f"{form.description.data} dönemi aidat borcunuz tanımlanmıştır.",
                        notification_type="dues", 
                        item_id=None
                    )
                except Exception as e:
                    current_app.logger.error(f"Toplu aidat push bildirimi gönderilemedi: {e}")

            flash(f"{len(residents)} sakine aidat başarıyla tanımlandı ve bildirim gönderildi.", "success")
            return redirect(url_for("admin.all_dues"))
        
        # --- SENARYO 2: TEK BİR SAKİNE AİDAT ATA (Değişiklik yok) ---
        else:
            if not form.user_id.data or form.user_id.data == 0:
                flash('Lütfen bir sakin seçin veya "Tüm Sakinlere Ata" kutusunu işaretleyin.', 'danger')
                return render_template("add_dues.html", form=form)

            selected_user = User.query.get(form.user_id.data)
            if not selected_user or selected_user.apartment_id != current_user.apartment_id:
                flash('Geçersiz kullanıcı seçimi.', 'danger')
                return render_template("add_dues.html", form=form)

            new_due = Dues(
                user_id=selected_user.id,
                amount=form.amount.data,
                description=form.description.data,
                due_date=form.due_date.data,
                apartment_id=selected_user.apartment_id
            )
            db.session.add(new_due)
            db.session.commit()
            
            # E-posta bildirimi gönder
            try:
                send_email(
                    to=selected_user.email,
                    subject=f"Yeni Aidat Bildirimi: {new_due.description}",
                    template='email/new_dues_notification',
                    resident_name=selected_user.name,
                    dues=new_due
                )
            except Exception as e:
                current_app.logger.error(f"Aidat e-postası gönderilemedi (Kullanıcı: {selected_user.id}): {e}")

            # Push bildirimi gönder
            try:
                send_push_notification(
                    user_id=selected_user.id,
                    title="Yeni Aidat Borcu",
                    body=f"{new_due.description} dönemi aidat borcunuz tanımlanmıştır.",
                    notification_type="dues", 
                    item_id=None
                )
            except Exception as e:
                current_app.logger.error(f"Aidat push bildirimi gönderilemedi (Kullanıcı: {selected_user.id}): {e}")

            flash("Aidat başarıyla eklendi ve sakine bildirim gönderildi.", "success")
            return redirect(url_for("admin.add_dues"))

    return render_template("add_dues.html", form=form)

@admin_bp.route('/receipts/<int:dues_id>/approve', methods=['POST'])
@login_required
@admin_required # admin_required decorator'ını kullanmak daha güvenli
def approve_receipt(dues_id):
    dues = Dues.query.get_or_404(dues_id)

    # Güvenlik Kontrolü: Admin, kendi apartmanındaki bir onayı mı yapıyor?
    if dues.apartment_id != current_user.apartment_id:
        flash("Bu işleme yetkiniz yok.", "danger")
        return redirect(url_for("admin.receipt_review"))

    if dues.is_paid:
        flash("Bu ödeme zaten daha önce onaylanmış.", "warning")
        return redirect(url_for("admin.receipt_review"))

    # Aidatı ve ödeme tarihini güncelle
    dues.is_paid = True
    dues.payment_date = datetime.utcnow()
    
    # Kasaya GELİR olarak yeni bir işlem oluştur
    income_transaction = Transaction(
        amount=dues.amount,
        description=f"Aidat Ödemesi: {dues.user.name} - {dues.description}",
        transaction_date=dues.payment_date,
        source_type='dues',
        source_id=dues.id,
        user_id=dues.user_id,
        apartment_id=dues.apartment_id
    )
    db.session.add(income_transaction)
    
    db.session.commit()

    # E-posta bildirimi gönder
    try:
        send_email(
            to=dues.user.email,
            subject=f"Ödemeniz Onaylandı: {dues.description}",
            template='email/payment_approved_notification',
            resident_name=dues.user.name,
            dues_description=dues.description
        )
    except Exception as e:
        current_app.logger.error(f"Ödeme onayı e-postası gönderilemedi (Kullanıcı: {dues.user.id}): {e}")

    # <-- YENİ EKLENEN PUSH BİLDİRİMİ KODU
    try:
        send_push_notification(
            user_id=dues.user.id,
            title="Ödemeniz Onaylandı",
            body=f'"{dues.description}" için yaptığınız ödeme yönetici tarafından onaylanmıştır.',
            notification_type="dues",
            item_id=None
        )
    except Exception as e:
        current_app.logger.error(f"Ödeme onayı push bildirimi gönderilemedi (Kullanıcı: {dues.user.id}): {e}")
    # --- EKLEME SONU ---
    
    flash("Ödeme başarıyla onaylandı ve sakine bildirim gönderildi.", "success")
    return redirect(url_for("admin.receipt_review"))



# =================================================================
# YENİ: Manuel Kasa İşlemi ekleme route ve fonksiyonu
# =================================================================
@admin_bp.route('/transaction/add', methods=['GET', 'POST'])
@login_required
def add_manual_transaction():
    if current_user.role != 'admin':
        flash("Bu sayfaya erişim yetkiniz yok.", 'danger')
        return redirect(url_for('resident.dashboard'))

    form = ManualTransactionForm()
    if form.validate_on_submit():
        if not current_user.apartment_id:
            flash("Apartman bilgisi eksik, işlem yapılamadı.", "danger")
            return redirect(url_for('expense.kasa_view'))  # ← yönlendirme buraya olabilir
        amount = form.amount.data
        # Eğer formdan 'gider' seçildiyse, tutarı negatife çevir
        if form.transaction_type.data == 'expense':
            amount = -amount
        
        new_transaction = Transaction(
            amount=amount,
            description=form.description.data,
            transaction_date=form.transaction_date.data,
            source_type='manual', # Kaynağın manuel olduğunu belirt
            user_id=current_user.id, # İşlemi yapan admin
            apartment_id=current_user.apartment_id
        )
        db.session.add(new_transaction)
        db.session.commit()
        flash('Manuel işlem başarıyla kasaya eklendi.', 'success')
        return redirect(url_for('expense.kasa_view'))

    return render_template('admin/add_manual_transaction.html', form=form)


# ... (Diğer tüm fonksiyonlarınızın geri kalanı)
@admin_bp.route("/dues/all")
@login_required
@admin_required # Yetki kontrolü için decorator kullanmak daha temiz
def all_dues():
    dues_list = Dues.query.filter_by(
        apartment_id=current_user.apartment_id
    ).order_by(Dues.due_date.desc()).all()
    return render_template("dues_admin_list.html", dues=dues_list)

@admin_bp.route("/dues/<int:dues_id>/toggle", methods=["POST"])
@login_required
@admin_required # Yetki kontrolü için decorator kullanmak daha temiz
def toggle_dues_status(dues_id):
    dues = Dues.query.get_or_404(dues_id)
    if dues.apartment_id != current_user.apartment_id:
        flash("Bu işleme yetkiniz yok.", "danger")
        return redirect(url_for("admin.all_dues"))

    dues.is_paid = not dues.is_paid
    dues.payment_date = datetime.utcnow() if dues.is_paid else None
    db.session.commit()
    flash("Aidat durumu güncellendi.", "success")
    return redirect(url_for("admin.all_dues"))

@admin_bp.route('/receipts/review')
@login_required
@admin_required # Rol kontrolünü decorator ile yapmak daha temiz ve güvenli
def receipt_review():
    """Yöneticiye, onay bekleyen makbuzları listeler."""
    
    # İYİLEŞTİRME: Yöneticinin sadece kendi apartmanındaki makbuzları görmesini sağla.
    dues_with_receipts = Dues.query.filter(
        Dues.apartment_id == current_user.apartment_id,
        Dues.receipt_filename.isnot(None), 
        Dues.is_paid == False
    ).order_by(Dues.receipt_upload_date.desc()).all()
    
    # DÜZELTME: CSRF koruması için boş formun bir örneğini oluşturuyoruz.
    form = CSRFProtectForm()
    
    # DÜZELTME: Oluşturduğumuz formu şablona gönderiyoruz.
    return render_template("receipt_review.html", dues_list=dues_with_receipts, form=form)

@admin_bp.route('/requests', methods=['GET'])
@login_required
@admin_required
def all_requests():
    # Sayfa numarası
    page = request.args.get('page', 1, type=int)
    per_page = 20  # her sayfada 20 kayıt

    # Temel sorgu: sadece bu admin'in apartmanındaki talepler
    query = (
        RequestModel.query
        .join(User, User.id == RequestModel.user_id)
        .filter(RequestModel.apartment_id == current_user.apartment_id)
        .order_by(RequestModel.created_at.desc())
    )

    # Filtreler
    category = (request.args.get('category') or '').strip()
    priority = (request.args.get('priority') or '').strip()
    status_txt = (request.args.get('status') or '').strip()
    # YENİ EKLENDİ: Arama kutusundan gelen veriyi alıyoruz.
    content_search = (request.args.get('content_search') or '').strip()

    if category:
        query = query.filter(RequestModel.category == category)

    if priority:
        query = query.filter(RequestModel.priority == priority)

    if status_txt:
        # Türkçe -> Enum eşlemesi
        status_map = {
            'Beklemede': RequestStatus.BEKLEMEDE,
            'İşlemde': RequestStatus.ISLEMDE,
            'Tamamlandı': RequestStatus.TAMAMLANDI,
        }
        status_enum = status_map.get(status_txt)
        if status_enum:
            query = query.filter(RequestModel.status == status_enum)

    # YENİ EKLENDİ: Eğer arama kutusu doluysa sorguya yeni bir filtre ekliyoruz.
    if content_search:
        search_term = f"%{content_search}%"
        query = query.filter(
            or_(
                RequestModel.title.ilike(search_term),
                RequestModel.description.ilike(search_term)
            )
        )

    # Sayfalama
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    requests_paginated = pagination.items

    # Not: pagination linklerinin de arama parametresini taşıması için
    # request.args'ı template'e göndermek en temiz yoldur.
    # Bu, request_list_admin.html dosyanızda zaten pagination linklerini
    # request.args.get('...') ile doldurduğunuz için çalışacaktır.
    return render_template(
        'admin/request_list_admin.html',
        requests=requests_paginated,
        pagination=pagination
    )




@admin_bp.route('/requests/<int:request_id>/reply', methods=['GET', 'POST'])
@login_required
def reply_request(request_id):
    if current_user.role != 'admin':
        flash("Yetkisiz erişim!", "danger")
        return redirect(url_for("resident.dashboard"))

    req = RequestModel.query.get_or_404(request_id)

    # 🔐 apartment_id kontrolü → farklı siteye müdahale engellenir
    if req.apartment_id != current_user.apartment_id:
        flash("Bu talebe yanıt verme yetkiniz yok.", "danger")
        return redirect(url_for("admin.all_requests"))

    reply_form = RequestReplyForm()
    status_form = UpdateRequestStatusForm(obj=req)

    if reply_form.validate_on_submit():
        req.reply = reply_form.reply.data
        req.status = RequestStatus.ISLEMDE
        req.updated_at = datetime.utcnow()
        db.session.commit()
        
        # E-posta bildirimi gönder
        try:
            send_email(
                to=req.user.email,
                subject=f"Talebinize Yanıt Verildi: {req.title}",
                template='email/request_reply_notification',
                resident_name=req.user.name,
                request_title=req.title,
                request_reply=req.reply,
                request_id=req.id 
            )
        except Exception as e:
            current_app.logger.error(f"Talep yanıtı e-postası gönderilemedi: {e}")
            
        # <-- YENİ EKLENEN PUSH BİLDİRİMİ KODU
        try:
            send_push_notification(
                user_id=req.user.id,
                title="Talebinize Yanıt Verildi",
                body=f'"{req.title}" başlıklı talebinize yönetici tarafından bir yanıt gönderildi.',
                notification_type="request_detail",
                item_id=req.id
            )
        except Exception as e:
            current_app.logger.error(f"Talep yanıtı push bildirimi gönderilemedi: {e}")
        # --- EKLEME SONU ---
            
        flash("Talebe yanıt gönderildi.", "success")
        return redirect(url_for('admin.all_requests'))

    return render_template('admin/reply_request.html', 
                           reply_form=reply_form, 
                           status_form=status_form, 
                           request=req)


@admin_bp.route('/requests/attachment/<int:request_id>')
@login_required
@admin_required
def download_request_attachment(request_id):
    """
    Yöneticinin, bir talebe eklenmiş dosyayı güvenli bir şekilde
    indirmesini sağlar. Doğrudan GCS linkine yönlendirir.
    """
    # 1. İlgili talebi veritabanından bul.
    req = RequestModel.query.get_or_404(request_id)

    # 2. Güvenlik Kontrolü: Yönetici bu talebi görmeye yetkili mi?
    if req.apartment_id != current_user.apartment_id:
        abort(403) # Yetkisiz erişim

    # 3. Talebe eklenmiş bir dosya var mı?
    if not req.attachment_url:
        flash("Bu talebe eklenmiş bir dosya bulunmuyor.", "warning")
        return redirect(url_for('admin.reply_request', request_id=req.id))

    # 4. Her şey yolundaysa, kullanıcıyı dosyanın GCS adresine yönlendir.
    #    Tarayıcı bu yönlendirmeyi takip ederek dosyayı açacak/indirecektir.
    return redirect(req.attachment_url)

@admin_bp.route('/requests/<int:request_id>/update_status', methods=['POST'])
@login_required
def update_request_status(request_id):
    if current_user.role != 'admin':
        return redirect(url_for('resident.dashboard'))
    
    req = RequestModel.query.get_or_404(request_id)

    # 🔐 apartment güvenlik kontrolü
    if req.apartment_id != current_user.apartment_id:
        flash("Bu talebe müdahale yetkiniz yok.", "danger")
        return redirect(url_for('admin.all_requests'))

    status_form = UpdateRequestStatusForm()

    if status_form.validate_on_submit():
        req.status = RequestStatus[status_form.status.data]
        req.updated_at = datetime.utcnow()
        db.session.commit()
        flash('Talep durumu güncellendi.', 'success')
    
    return redirect(url_for('admin.reply_request', request_id=req.id))

@admin_bp.route("/polls/create", methods=["GET", "POST"])
@login_required
@admin_required
def create_poll():
    form = PollCreateForm()

    if form.validate_on_submit():
        try:
            # 1. Anketi oluştur
            new_poll = Poll(
                question=form.question.data,
                created_by_id=current_user.id,
                apartment_id=current_user.apartment_id,
                is_active=True,
                expiration_date=form.expiration_date.data
            )
            db.session.add(new_poll)
            
            # 2. Seçenekleri ekle
            for option_form in form.options.data:
                if option_form['text'].strip():
                    db.session.add(PollOption(
                        text=option_form['text'].strip(),
                        poll=new_poll
                    ))
            
            # ID'nin oluşması için veritabanına ön kayıt yap
            db.session.flush()

            # 3. Bildirim gönderilecek sakinleri bul
            residents = User.query.filter_by(
                apartment_id=current_user.apartment_id, 
                role='resident',
                is_active=True
            ).all()

            # E-posta için gerekli veriyi hazırla
            poll_data = {
                "id": new_poll.id,
                "question": new_poll.question,
                "vote_link": url_for('poll.view_poll', poll_id=new_poll.id, _external=True)
            }

            # 4. Her bir sakine döngü ile e-posta gönder
            for resident in residents:
                if resident.email:
                    try:
                        send_email(
                            to=resident.email,
                            subject=f"Yeni Anket: {new_poll.question[:45]}...",
                            template='email/new_poll_notification',
                            resident_name=resident.name,
                            poll=poll_data,
                            current_year=datetime.utcnow().year
                        )
                    except Exception as e:
                        current_app.logger.error(f"Anket e-postası gönderilemedi (Kullanıcı: {resident.id}): {e}")

            # Şimdi tek seferde toplu push bildirimi gönder
            try:
                # <<< GÜNCELLEME BURADA BAŞLIYOR >>>
                send_notification_to_users(
                    users=residents,
                    title="Yeni Anket Yayında",
                    body=f'"{new_poll.question}" sorulu yeni bir anket oylamaya açılmıştır.',
                    notification_type="polls", # 'poll_detail' -> 'polls' olarak değiştirildi
                    item_id=None # Anket ID'si kaldırıldı, çünkü ana listeye gidiyor
                )
                # <<< GÜNCELLEME BİTTİ >>>
            except Exception as e:
                current_app.logger.error(f"Toplu anket push bildirimi gönderilemedi: {e}")

            db.session.commit()
            flash(f"Anket oluşturuldu ve {len(residents)} sakine bildirim gönderildi.", "success")
            return redirect(url_for('admin.dashboard'))

        except Exception as e:
            db.session.rollback()
            current_app.logger.critical(f"Anket oluşturulamadı: {str(e)}", exc_info=True)
            flash("Sistem hatası! Anket oluşturulamadı.", "danger")
            return redirect(url_for('admin.dashboard'))

    return render_template("admin/create_poll.html", form=form)





# =================================================================
# YENİ: Ortak Alan Yönetimi Rotaları
# =================================================================
@admin_bp.route("/common-areas/add", methods=['GET', 'POST'])
@login_required
@admin_required
def add_common_area():
    """Yöneticinin yeni bir ortak alan eklemesini sağlar."""
    form = CommonAreaForm()
    if form.validate_on_submit():
        # Yeni CommonArea nesnesini formdan gelen verilerle oluştur.
        new_area = CommonArea(
            name=form.name.data,
            description=form.description.data,
            is_active=form.is_active.data,
            apartment_id=current_user.apartment_id # Alanı yöneticinin apartmanına bağla
        )
        db.session.add(new_area)
        db.session.commit()
        flash(f"'{new_area.name}' adlı ortak alan başarıyla oluşturuldu.", "success")
        # Şimdilik admin paneline yönlendirelim. Sonra liste sayfasına yönlendiririz.
        return redirect(url_for('admin.dashboard'))

    return render_template("admin/common_area_form.html", 
                           title="Yeni Ortak Alan Ekle", 
                           form=form)

@admin_bp.route('/dues-board')
@login_required
@admin_required
def dues_board():
    """Yöneticinin, apartmandaki tüm borçluları ve borç durumlarını gördüğü pano."""
    
    unpaid_dues = Dues.query.options(joinedload(Dues.user)).filter_by(
        apartment_id=current_user.apartment_id, 
        is_paid=False
    ).order_by(Dues.due_date).all()
    
    debtors_summary = {}

    for due in unpaid_dues:
        if due.user_id not in debtors_summary:
            debtors_summary[due.user_id] = {
                'name': due.user.name, # Sadece 'name' kullanılıyor, 'surname' kaldırıldı.
                'unpaid_periods': [],
                'total_debt': 0.0
            }
        
        debtors_summary[due.user_id]['unpaid_periods'].append(due.description or due.due_date.strftime('%B %Y'))
        debtors_summary[due.user_id]['total_debt'] += float(due.amount)

    return render_template('admin/dues_board.html', 
                           title="Genel Aidat Panosu",
                           debtors=debtors_summary.values())

# =================================================================
# YENİ: Usta Yönetimi Rotaları
# =================================================================
@admin_bp.route("/craftsmen", methods=['GET', 'POST'])
@login_required
@admin_required
def manage_craftsmen():
    """Yöneticinin usta eklemesini ve listelemesini sağlayan sayfa."""
    form = CraftsmanForm()
    csrf_form = CSRFProtectForm()
    
    if form.validate_on_submit():
        # Formdan gelen verilerle yeni bir Craftsman nesnesi oluştur
        new_craftsman = Craftsman(
            apartment_id=current_user.apartment_id,  # Ustayı yöneticinin apartmanına ata
            specialty=form.specialty.data,
            full_name=form.full_name.data,
            phone_number=form.phone_number.data,
            notes=form.notes.data
        )
        db.session.add(new_craftsman)
        db.session.commit()
        flash('Yeni usta başarıyla eklendi.', 'success')
        return redirect(url_for('admin.manage_craftsmen'))

    # GET isteği için, mevcut apartmana ait tüm ustaları listele
    craftsmen = Craftsman.query.filter_by(
        apartment_id=current_user.apartment_id
    ).order_by(Craftsman.specialty).all()
    
    return render_template('admin/manage_craftsmen.html', 
                           title="Usta Yönetimi", 
                           form=form, 
                           craftsmen=craftsmen,
                           csrf_form=csrf_form)


@admin_bp.route("/craftsmen/<int:craftsman_id>/delete", methods=['POST'])
@login_required
@admin_required
def delete_craftsman(craftsman_id):
    """Belirli bir ustayı veritabanından siler."""
    # Silinecek ustayı ID'si ile bul, bulamazsan 404 hatası ver
    craftsman_to_delete = Craftsman.query.get_or_404(craftsman_id)

    # GÜVENLİK KONTROLÜ: Admin, sadece kendi apartmanındaki bir ustayı silebilir.
    if craftsman_to_delete.apartment_id != current_user.apartment_id:
        abort(403) # Yetkisiz erişim denemesini engelle

    db.session.delete(craftsman_to_delete)
    db.session.commit()
    flash('Usta başarıyla silindi.', 'success')
    return redirect(url_for('admin.manage_craftsmen'))

# ====================================
# YÖNETİCİ ONAY SİSTEMİ
# ====================================

@admin_bp.route('/users/pending')
@login_required
@admin_required
def pending_users():
    """Yöneticinin kendi apartmanına kayıt olmuş ve onayı bekleyen kullanıcıları listeler."""
    
    # Yöneticinin apartmanındaki, is_active=False olan tüm kullanıcıları bul.
    users_to_approve = User.query.filter_by(
        apartment_id=current_user.apartment_id,
        is_email_verified=True,
        is_active=False
    ).order_by(User.created_at.desc()).all()
    
    # Onay ve Reddet butonları için CSRF koruması
    csrf_form = CSRFProtectForm()

    return render_template('admin/pending_users.html', 
                           title="Onay Bekleyen Kullanıcılar", 
                           users=users_to_approve,
                           csrf_form=csrf_form)


@admin_bp.route('/users/<int:user_id>/approve', methods=['POST'])
@login_required
@admin_required
def approve_user(user_id):
    """Belirtilen kullanıcının hesabını aktif eder."""
    user_to_approve = User.query.get_or_404(user_id)

    # GÜVENLİK KONTROLÜ: Yönetici, sadece kendi apartmanındaki bir kullanıcıyı onaylayabilir.
    if user_to_approve.apartment_id != current_user.apartment_id:
        flash("Bu kullanıcıyı onaylama yetkiniz yok.", "danger")
        return redirect(url_for('admin.pending_users'))

    # Kullanıcıyı aktif et
    user_to_approve.is_active = True
    db.session.commit()

    # Kullanıcıya hesabının onaylandığına dair bir e-posta gönder
    try:
        send_email(
            to=user_to_approve.email,
            subject='Hesabınız Onaylandı!',
            template='email/account_approved',
            user=user_to_approve
        )
    except Exception as e:
        current_app.logger.error(f"Hesap onayı e-postası gönderilemedi: {e}")

    # <<< PUSH BİLDİRİMİ KOD BLOĞU BURADAN SİLİNDİ >>>

    flash(f"'{user_to_approve.name}' adlı kullanıcının hesabı başarıyla onaylandı.", 'success')
    return redirect(url_for('admin.pending_users'))

@admin_bp.route('/users/<int:user_id>/reject', methods=['POST'])
@login_required
@admin_required
def reject_user(user_id):
    """Belirtilen kullanıcının kaydını silerek reddeder."""
    user_to_reject = User.query.get_or_404(user_id)

    # GÜVENLİK KONTROLÜ: Yönetici, sadece kendi apartmanındaki bir kullanıcıyı reddedebilir.
    if user_to_reject.apartment_id != current_user.apartment_id:
        flash("Bu kullanıcıyı reddetme yetkiniz yok.", "danger")
        return redirect(url_for('admin.pending_users'))

    # Kullanıcıyı veritabanından sil
    user_name = user_to_reject.name
    db.session.delete(user_to_reject)
    db.session.commit()

    flash(f"'{user_name}' adlı kullanıcının kaydı reddedildi ve silindi.", 'info')
    return redirect(url_for('admin.pending_users'))

# =================================================================
# YENİ: BLOG YÖNETİMİ ROTALARI
# =================================================================

@admin_bp.route("/blog/posts")
@login_required
@admin_required
def list_posts():
    """Yöneticinin tüm blog yazılarını (taslak ve yayınlanmış) listeler."""
    posts = Post.query.filter_by(
        apartment_id=current_user.apartment_id
    ).order_by(Post.created_at.desc()).all()
    
    # Bu sayfada silme işlemi için bir CSRF formu da göndereceğiz.
    csrf_form = CSRFProtectForm()
    
    return render_template("admin/list_posts.html", posts=posts, csrf_form=csrf_form, title="Blog Yazılarını Yönet")

@admin_bp.route("/blog/add", methods=['GET', 'POST'])
@login_required
@admin_required
def add_post():
    """Yöneticinin yeni bir blog yazısı eklemesini sağlar."""
    form = PostForm()
    if form.validate_on_submit():
        try:
            image_url = None
            # 1. Formdan bir resim dosyası gelip gelmediğini kontrol et
            if form.image.data:
                image_file = form.image.data
                # 2. Resmi Google Cloud Storage'a 'blog_images' klasörüne yükle
                image_url = upload_to_gcs(image_file, 'blog_images')
                if not image_url:
                    flash("Resim yüklenirken bir hata oluştu. Lütfen tekrar deneyin.", "danger")
                    return render_template("admin/add_post.html", form=form, title="Yeni Blog Yazısı Ekle")

            formatted_slug = form.slug.data.lower().replace(" ", "-")

            new_post = Post(
                title=form.title.data,
                content=form.content.data,
                slug=formatted_slug,
                is_published=form.is_published.data,
                image_url=image_url,  # <-- YENİ: Resim URL'sini veritabanına ekle
                author_id=current_user.id,
                apartment_id=current_user.apartment_id
            )
            db.session.add(new_post)
            db.session.commit()
            flash("Yeni blog yazısı başarıyla kaydedildi.", "success")
            return redirect(url_for('admin.list_posts'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Blog yazısı oluşturulamadı: {e}")
            flash("Yazı kaydedilirken bir hata oluştu. URL uzantısının (slug) başka bir yazıyla aynı olmadığından emin olun.", "danger")

    return render_template("admin/add_post.html", form=form, title="Yeni Blog Yazısı Ekle")

@admin_bp.route("/blog/edit/<int:post_id>", methods=['GET', 'POST'])
@login_required
@admin_required
def edit_post(post_id):
    """Mevcut bir blog yazısını düzenler."""
    post = Post.query.get_or_404(post_id)
    if post.apartment_id != current_user.apartment_id:
        abort(403)

    form = PostForm(obj=post)
    if form.validate_on_submit():
        try:
            # 1. Formdan YENİ bir resim dosyası gelip gelmediğini kontrol et
            if form.image.data:
                image_file = form.image.data
                # 2. Yeni resmi Google Cloud Storage'a yükle
                new_image_url = upload_to_gcs(image_file, 'blog_images')
                if new_image_url:
                    # Sadece yükleme başarılı olursa mevcut resim URL'sini güncelle
                    post.image_url = new_image_url
                else:
                    flash("Yeni resim yüklenirken bir hata oluştu. Resim güncellenmedi.", "warning")
            
            post.title = form.title.data
            post.content = form.content.data
            post.slug = form.slug.data.lower().replace(" ", "-")
            post.is_published = form.is_published.data
            db.session.commit()
            flash("Yazı başarıyla güncellendi.", "success")
            return redirect(url_for('admin.list_posts'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Blog yazısı güncellenemedi: {e}")
            flash("Yazı güncellenirken bir hata oluştu. URL uzantısının (slug) başka bir yazıyla aynı olmadığından emin olun.", "danger")

    return render_template("admin/edit_post.html", form=form, title="Yazıyı Düzenle", post=post)


@admin_bp.route("/blog/delete/<int:post_id>", methods=['POST'])
@login_required
@admin_required
def delete_post(post_id):
    """Bir blog yazısını siler."""
    post = Post.query.get_or_404(post_id)
    # Güvenlik kontrolü
    if post.apartment_id != current_user.apartment_id:
        abort(403)
    
    try:
        db.session.delete(post)
        db.session.commit()
        flash("Yazı başarıyla silindi.", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Blog yazısı silinemedi: {e}")
        flash("Yazı silinirken bir hata oluştu.", "danger")
        
    return redirect(url_for('admin.list_posts'))



@admin_bp.route("/recurring-expenses", methods=['GET', 'POST'])
@login_required
@admin_required
def manage_recurring_expenses():
    """Yöneticinin otomatik gider kurallarını eklemesini ve listelemesini sağlar."""
    form = RecurringExpenseForm()
    if form.validate_on_submit():
        # Yeni kuralı form verileriyle oluştur
        new_rule = RecurringExpense(
            apartment_id=current_user.apartment_id,
            description=form.description.data,
            amount=form.amount.data,
            day_of_month=form.day_of_month.data,
            is_active=form.is_active.data
        )
        db.session.add(new_rule)
        db.session.commit()
        flash("Yeni tekrarlayan gider kuralı başarıyla oluşturuldu.", "success")
        return redirect(url_for('admin.manage_recurring_expenses'))

    # Sayfa yüklendiğinde (GET isteği), mevcut tüm kuralları veritabanından çek
    rules = RecurringExpense.query.filter_by(apartment_id=current_user.apartment_id).order_by(RecurringExpense.day_of_month).all()

    # Hem formu hem de kurallar listesini şablona gönder
    return render_template("admin/manage_recurring_expenses.html", 
                           title="Otomatik Tekrarlayan Giderler", 
                           form=form, 
                           rules=rules)

@admin_bp.route('/tasks/generate-recurring-dues')
def generate_recurring_dues():
    """
    App Engine Cron Job tarafından her gün tetiklenmek üzere tasarlanmıştır.
    O gün oluşturulması gereken tüm tekrarlayan aidatları oluşturur.
    """
    # GÜVENLİK: Bu isteğin sadece Google App Engine Cron servisinden geldiğini doğrula.
    # Bu, dışarıdan herhangi birinin bu URL'yi çalıştırıp sürekli aidat oluşturmasını engeller.
    if 'X-Appengine-Cron' not in request.headers:
        current_app.logger.warning("Yetkisiz cron job denemesi engellendi.")
        return "Forbidden", 403

    today_day_number = datetime.utcnow().day
    
    # Bugünün gün numarasına ayarlanmış ve aktif olan tüm kuralları veritabanından bul
    rules_to_run = RecurringExpense.query.filter_by(day_of_month=today_day_number, is_active=True).all()
    
    current_app.logger.info(f"Cron job çalıştı. Bugünün günü: {today_day_number}. Çalıştırılacak kural sayısı: {len(rules_to_run)}")

    for rule in rules_to_run:
        # Kuralın ait olduğu apartmandaki tüm aktif sakinleri bul
        residents = User.query.filter_by(apartment_id=rule.apartment_id, role='resident', is_active=True).all()
        
        for resident in residents:
            # EN ÖNEMLİ KONTROL: Mükerrer kaydı önle!
            # Bu ay için bu kuraldan bu sakine daha önce bir aidat oluşturulmuş mu?
            start_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            existing_due = Dues.query.filter(
                Dues.user_id == resident.id,
                Dues.description == rule.description,
                Dues.created_at >= start_of_month 
            ).first()

            # Eğer bu ay içinde bu aidat daha önce oluşturulmadıysa, şimdi oluştur.
            if not existing_due:
                try:
                    # Yeni aidat borcunu oluştur
                    new_due = Dues(
                        user_id=resident.id,
                        apartment_id=resident.apartment_id,
                        amount=rule.amount,
                        description=rule.description,
                        due_date=datetime.utcnow().date(), # Son ödeme tarihini istediğiniz gibi ayarlayabilirsiniz
                        created_at=datetime.utcnow() # Mükerrer kontrol için bu tarih önemli
                    )
                    db.session.add(new_due)
                    
                    # Sakine e-posta gönder
                    send_email(
                        to=resident.email,
                        subject=f"Yeni Aidat Bildirimi: {new_due.description}",
                        template='email/new_dues_notification',
                        resident_name=resident.name,
                        dues=new_due
                    )
                    current_app.logger.info(f"Aidat oluşturuldu: Kullanıcı {resident.id}, Kural {rule.id}")
                except Exception as e:
                    current_app.logger.error(f"Otomatik aidat oluşturulurken hata: {e}")
    
    # Tüm işlemler bittikten sonra veritabanına kaydet
    db.session.commit()
    
    # Cron servisine işlemin başarılı olduğunu bildir
    return "OK", 200

@admin_bp.route("/content")
@login_required
@admin_required
def manage_content():
    """Yönetilebilir tüm dinamik içerikleri listeler."""
    contents = DynamicContent.query.order_by(DynamicContent.title).all()
    return render_template("admin/manage_content.html", 
                           contents=contents, 
                           title="İçerik Yönetimi")

@admin_bp.route("/content/edit/<string:key>", methods=['GET', 'POST'])
@login_required
@admin_required
def edit_content(key):
    """Belirli bir dinamik içeriği düzenler."""
    # Düzenlenecek içeriği 'key' ile veritabanından bul
    content_obj = DynamicContent.query.filter_by(key=key).first_or_404()
    
    # Formu, veritabanından gelen mevcut verilerle doldur
    form = DynamicContentForm(obj=content_obj)

    if form.validate_on_submit():
        try:
            # Formdan gelen yeni verileri veritabanı nesnesine aktar
            content_obj.title = form.title.data
            content_obj.content = form.content.data
            db.session.commit()
            flash(f"'{content_obj.title}' başlıklı içerik başarıyla güncellendi.", "success")
            return redirect(url_for('admin.manage_content'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"İçerik güncellenirken hata: {e}")
            flash("İçerik güncellenirken bir hata oluştu.", "danger")

    return render_template("admin/edit_content.html", 
                           form=form, 
                           title=f"İçeriği Düzenle: {content_obj.title}")

@admin_bp.route('/tasks/check-expired-polls')
def check_expired_polls():
    """
    App Engine Cron Job tarafından her gün tetiklenmek üzere tasarlanmıştır.
    Süresi dolmuş ve sonuç bildirimi henüz gönderilmemiş anketleri bulur
    ve oylamaya katılan tüm sakinlere bildirim gönderir.
    """
    # GÜVENLİK: Bu isteğin sadece Google App Engine Cron servisinden geldiğini doğrula.
    if 'X-Appengine-Cron' not in request.headers:
        current_app.logger.warning("Yetkisiz anket sonuçları cron job denemesi engellendi.")
        return "Forbidden", 403

    try:
        now = datetime.utcnow()
        
        # Süresi dolmuş VE sonuç bildirimi gönderilmemiş anketleri bul
        expired_polls = Poll.query.filter(
            Poll.expiration_date <= now,
            Poll.result_notification_sent == False
        ).all()
        
        current_app.logger.info(f"Anket sonuçları cron job çalıştı. {len(expired_polls)} adet süresi dolmuş anket bulundu.")

        if not expired_polls:
            return "No expired polls to process.", 200

        for poll in expired_polls:
            # 1. Bu ankete oy veren tüm kullanıcıların ID'lerini bul (tekrar edenleri engelle)
            voter_ids_tuples = db.session.query(Vote.user_id).filter_by(poll_id=poll.id).distinct().all()
            user_ids_to_notify = [v_id for v_id, in voter_ids_tuples]
            
            current_app.logger.info(f"Anket #{poll.id} için {len(user_ids_to_notify)} katılımcıya bildirim gönderilecek.")

            # 2. Eğer oy veren varsa, bu kullanıcıların User nesnelerini tek bir sorgu ile çek
            if user_ids_to_notify:
                users_to_notify = User.query.filter(User.id.in_(user_ids_to_notify)).all()
                
                # 3. Tek seferde toplu push bildirimi gönder
                try:
                    send_notification_to_users(
                        users=users_to_notify,
                        title="Anket Sonuçlandı",
                        body=f'"{poll.question}" sorulu anketin oylaması tamamlandı. Sonuçları görmek için tıklayın.',
                        notification_type="poll_detail",
                        item_id=poll.id
                    )
                except Exception as e:
                    current_app.logger.error(f"Toplu anket sonucu push bildirimi gönderilemedi (Anket ID: {poll.id}): {e}")
            
            # 4. Bildirimler gönderildikten sonra anketi "gönderildi" olarak işaretle
            poll.result_notification_sent = True
        
        # 5. Tüm değişiklikleri veritabanına kaydet
        db.session.commit()
        
        return f"Processed {len(expired_polls)} polls.", 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Anket sonuçları cron job çalışırken hata oluştu: {e}")
        return "An error occurred.", 500
