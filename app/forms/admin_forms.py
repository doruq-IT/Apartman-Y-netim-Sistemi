# forms/admin_forms.py

from flask_wtf import FlaskForm
from wtforms import StringField, DecimalField, DateField, SubmitField, SelectField, TextAreaField, RadioField, BooleanField, IntegerField
from wtforms.validators import DataRequired, Length, NumberRange
from ..models import RequestStatus
from datetime import datetime
from flask_wtf.file import FileField, FileAllowed


class AddDuesForm(FlaskForm):
    title = StringField("Başlık", validators=[DataRequired(), Length(max=100)])
    amount = DecimalField("Tutar (₺)", validators=[DataRequired(), NumberRange(min=0)], places=2)
    due_date = DateField("Son Ödeme Tarihi", format='%Y-%m-%d', validators=[DataRequired()])
    submit = SubmitField("Aidat Oluştur")


class UpdateRequestStatusForm(FlaskForm):
    """Adminin bir talebin durumunu değiştirmesi için kullanılan form."""
    status = SelectField('Durum', 
                         choices=[(status.name, status.value) for status in RequestStatus])
    submit = SubmitField('Durumu Güncelle')


class ExpenseForm(FlaskForm):
    description = TextAreaField('Masraf Açıklaması', validators=[DataRequired()])
    amount = DecimalField('Tutar (₺)', validators=[DataRequired(), NumberRange(min=0)])
    expense_date = DateField('Masraf Tarihi', format='%Y-%m-%d', validators=[DataRequired()])
    invoice = FileField('Fatura/Fiş Yükle (Opsiyonel)', validators=[
        FileAllowed(['jpg', 'png', 'jpeg', 'pdf'], 'Sadece resim veya PDF dosyaları yüklenebilir!')
    ])
    submit = SubmitField('Masrafı Kaydet')


# <-- YENİ EKLENEN FORM SINIFI
class ExpenseEditForm(FlaskForm):
    """Mevcut bir gidere fatura yüklemek/güncellemek için kullanılan form."""
    invoice = FileField('Yeni Fatura Dosyası (JPG, PNG, PDF)', validators=[
        FileAllowed(['jpg', 'png', 'jpeg', 'pdf'], 'Sadece resim ve PDF dosyaları yüklenebilir!')
    ])
    submit = SubmitField('Faturayı Kaydet')
# --- EKLEME SONU ---


class ManualTransactionForm(FlaskForm):
    """Adminin kasaya manuel gelir/gider eklemesi için form."""
    description = TextAreaField('İşlem Açıklaması', 
                                 validators=[DataRequired()], 
                                 render_kw={"placeholder": "Örn: Açılış Bakiyesi, Banka Faiz Geliri, Düzeltme..."})
    amount = DecimalField('Tutar (₺)', validators=[DataRequired(), NumberRange(min=0.01)])
    transaction_date = DateField('İşlem Tarihi', format='%Y-%m-%d', validators=[DataRequired()], default=datetime.utcnow)
    transaction_type = RadioField('İşlem Türü', 
                                  choices=[('income', 'Gelir (Kasa Girişi)'), ('expense', 'Gider (Kasa Çıkışı)')],
                                  validators=[DataRequired()])
    submit = SubmitField('İşlemi Kaydet')


class ApartmentForm(FlaskForm):
    """Yeni bir apartman/site kaydı oluşturma formu."""
    name = StringField('Apartman / Site Adı', validators=[DataRequired(), Length(min=3, max=150)])
    address = TextAreaField('Adres', render_kw={"rows": 4})
    submit = SubmitField('Apartmanı Oluştur')


class CSRFProtectForm(FlaskForm):
    """
    Sadece CSRF token'ı sağlamak için kullanılan boş bir form.
    Bu, "Onayla" gibi tekil butonların güvenliğini sağlamak için gereklidir.
    """
    pass

class FinancialReportForm(FlaskForm):
    start_date = DateField('Başlangıç Tarihi', validators=[DataRequired()], format='%Y-%m-%d')
    end_date = DateField('Bitiş Tarihi', validators=[DataRequired()], format='%Y-%m-%d')
    submit = SubmitField('Rapor Oluştur')
    
class CommonAreaForm(FlaskForm):
    # Süper Yönetici için apartman seçim alanı
    apartment_id = SelectField('Apartman', coerce=int, validators=[DataRequired(message="Lütfen bir apartman seçin.")])
    name = StringField('Alan Adı', validators=[DataRequired(), Length(max=100)])
    description = TextAreaField('Açıklama', render_kw={"rows": 3})
    is_active = BooleanField('Aktif', default=True)
    submit = SubmitField('Kaydet')


class CraftsmanForm(FlaskForm):
    """Yöneticinin yeni bir usta eklemesi için kullanılan form."""
    specialty = StringField('Uzmanlık Alanı', 
                            validators=[DataRequired(), Length(max=100)],
                            render_kw={"placeholder": "Örn: Elektrik Tesisatçısı, Boyacı"})
    full_name = StringField('Adı Soyadı', validators=[DataRequired(), Length(max=150)])
    phone_number = StringField('Telefon Numarası', validators=[DataRequired(), Length(max=20)])
    notes = TextAreaField('Notlar (Opsiyonel)', 
                          render_kw={"rows": 3, "placeholder": "Örn: Sadece hafta içi çalışır, tavsiye üzerine..."})
    submit = SubmitField('Ustayı Kaydet')


class RecurringExpenseForm(FlaskForm):
    description = StringField("Açıklama (Örn: Aylık Aidat)", validators=[DataRequired()])
    amount = DecimalField("Tutar (₺)", validators=[DataRequired(), NumberRange(min=0)])
    day_of_month = IntegerField("Ayın Hangi Günü Otomatik Oluşturulsun?", 
                                validators=[DataRequired(), NumberRange(min=1, max=28, message="Lütfen 1 ile 28 arasında bir gün girin.")])
    is_active = BooleanField("Bu Kural Aktif Olsun", default=True)
    submit = SubmitField("Kuralı Kaydet")


class DynamicContentForm(FlaskForm):
    """Dinamik içerikleri (kurallar vb.) düzenlemek için yönetici formu."""
    title = StringField('Başlık', validators=[DataRequired()])
    content = TextAreaField('İçerik (HTML formatında düzenleyebilirsiniz)', 
                            validators=[DataRequired()], 
                            render_kw={'rows': 20})
    submit = SubmitField('İçeriği Güncelle')
