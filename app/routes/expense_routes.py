# Gerekli yeni modülleri import ediyoruz
from flask import Blueprint, render_template, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from app.models import Expense, Transaction
from app.extensions import db
from sqlalchemy import func
# Adım 2'de oluşturduğumuz yeni formu import ediyoruz
from app.forms.admin_forms import ExpenseEditForm
# Google Cloud Storage'a yükleme yapmak için yardımcı fonksiyonumuzu import ediyoruz
from app.gcs_utils import upload_to_gcs

# Masraflar için yeni bir Blueprint oluşturuyoruz
expense_bp = Blueprint('expense', __name__)

@expense_bp.route('/expenses', methods=['GET'])
@login_required
def expense_list():
    """Tüm apartman masraflarını listeleyen sayfa."""
    
    # Tüm masrafları tarihe göre en yeniden eskiye doğru sırala
    expenses = Expense.query \
        .filter_by(apartment_id=current_user.apartment_id) \
        .order_by(Expense.expense_date.desc()) \
        .all()
    
    # Verileri, daha önce oluşturduğumuz şablona gönder
    return render_template('expenses/expense_list.html', expenses=expenses)


# <-- YENİ EKLENEN FONKSİYON BAŞLANGICI
@expense_bp.route('/expenses/edit/<int:expense_id>', methods=['GET', 'POST'])
@login_required
def edit_expense(expense_id):
    """Mevcut bir gidere sonradan fatura eklemeyi veya faturasını güncellemeyi sağlar."""
    # Sadece adminlerin bu sayfaya erişebilmesi için kontrol
    if current_user.role != 'admin':
        abort(403)

    # Düzenlenecek gideri veritabanından bul, bulamazsan 404 hatası ver
    expense = Expense.query.get_or_404(expense_id)

    # GÜVENLİK KONTROLÜ: Yönetici, sadece kendi apartmanındaki bir gideri düzenleyebilir.
    if expense.apartment_id != current_user.apartment_id:
        abort(403)

    # Adım 2'de oluşturduğumuz formu çağır
    form = ExpenseEditForm()

    if form.validate_on_submit():
        # Formdan bir dosya yüklendi mi diye kontrol et
        if form.invoice.data:
            uploaded_file = form.invoice.data
            # Dosyayı Google Cloud Storage'a 'invoices' klasörüne yükle
            invoice_url = upload_to_gcs(uploaded_file, 'invoices')
            
            if invoice_url:
                # Yükleme başarılıysa, giderin fatura bilgisini veritabanında güncelle
                expense.invoice_filename = invoice_url
                db.session.commit()
                flash('Fatura başarıyla yüklendi ve gidere eklendi.', 'success')
            else:
                flash('Fatura yüklenirken bir hata oluştu. Lütfen tekrar deneyin.', 'danger')
            
            # İşlem bittikten sonra gider listesi sayfasına geri dön
            return redirect(url_for('expense.expense_list'))

    # Eğer sayfa ilk defa açılıyorsa (GET isteği), düzenleme şablonunu göster
    return render_template('expenses/edit_expense.html', 
                           form=form, 
                           expense=expense, 
                           title="Gideri Düzenle")
# --- YENİ EKLENEN FONKSİYON SONU ---


@expense_bp.route('/kasa', methods=['GET'])
@login_required
def kasa_view():
    """Kasa bakiyesini ve tüm işlemleri (gelir/gider) listeleyen sayfa."""

    current_balance = db.session.query(func.sum(Transaction.amount)) \
        .filter(Transaction.apartment_id == current_user.apartment_id) \
        .scalar() or 0.0

    transactions = Transaction.query \
        .filter_by(apartment_id=current_user.apartment_id) \
        .order_by(Transaction.transaction_date.desc()) \
        .all()

    # Hem bakiyeyi hem de işlem listesini şablona gönder
    return render_template('kasa/kasa_view.html', 
                           transactions=transactions, 
                           balance=current_balance)
