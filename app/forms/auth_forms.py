from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField, SelectField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional, Regexp

# --- Hata Mesajları için Ortak Değişkenler ---
MSG_REQUIRED = "Bu alan zorunludur."
MSG_EMAIL = "Lütfen geçerli bir e-posta adresi girin."
MSG_PASSWORDS_MATCH = "Şifreler eşleşmiyor."

class RegisterForm(FlaskForm):
    """Kullanıcı kayıt formu."""
    first_name = StringField(
        "Ad", 
        validators=[DataRequired(MSG_REQUIRED), Length(min=2, max=50)]
    )
    last_name = StringField(
        "Soyad", 
        validators=[DataRequired(MSG_REQUIRED), Length(min=2, max=50)]
    )
    email = StringField(
        "E-posta", 
        validators=[DataRequired(MSG_REQUIRED), Email(message=MSG_EMAIL)]
    )
    phone_number = StringField(
        'Telefon Numarası',
        validators=[
            DataRequired(MSG_REQUIRED), # 'Optional()' yerine 'DataRequired' ekleyerek zorunlu yaptık.
            Regexp(r'^\d{10}$', message="Lütfen 10 haneli telefon numaranızı girin. Örn: 5xxxxxxxxx")
        ]
    )
    # Apartman seçimi için açılır menü. Seçenekleri route içerisinden doldurulacak.
    apartment_id = SelectField(
        'Apartman', 
        coerce=int, 
        validators=[DataRequired(message="Lütfen bir apartman seçin.")]
    )
    block_id = SelectField(
        'Blok', 
        coerce=int, 
        validators=[Optional()]
    )
    daire_no = StringField(
        'Daire Numarası',
        validators=[DataRequired(MSG_REQUIRED), Length(max=20)]
    )
    # GÜNCELLENDİ: Şifre uzunluğu 8 karaktere çıkarıldı.
    password = PasswordField(
        "Şifre", 
        validators=[DataRequired(MSG_REQUIRED), Length(min=8, message="Şifreniz en az 8 karakter olmalıdır.")]
    )
    confirm_password = PasswordField(
        "Şifre Tekrar", 
        validators=[DataRequired(MSG_REQUIRED), EqualTo("password", message=MSG_PASSWORDS_MATCH)]
    )
    # GÜNCELLENDİ: Validator'a özel hata mesajı eklendi.
    accept_terms = BooleanField(
        "Şartları kabul ediyorum", 
        validators=[DataRequired(message="Kayıt olmak için kullanım şartlarını kabul etmelisiniz.")]
    )
    accept_kvkk = BooleanField(
        "KVKK Metnini kabul ediyorum", 
        validators=[DataRequired(message="Kayıt olmak için KVKK metnini onaylamalısınız.")]
    )
    submit = SubmitField("Hesabımı Oluştur")


class LoginForm(FlaskForm):
    """Kullanıcı giriş formu."""
    email = StringField(
        "E-posta", 
        validators=[DataRequired(MSG_REQUIRED), Email(message=MSG_EMAIL)]
    )
    password = PasswordField(
        "Şifre", 
        validators=[DataRequired(MSG_REQUIRED)]
    )
    remember = BooleanField("Beni Hatırla")
    submit = SubmitField("Giriş Yap")


class ProfileEditForm(FlaskForm):
    """Kullanıcı profil düzenleme formu."""
    name = StringField(
        "Ad Soyad", 
        validators=[DataRequired(MSG_REQUIRED)]
    )
    email = StringField(
        "E-posta", 
        validators=[DataRequired(MSG_REQUIRED), Email(message=MSG_EMAIL)]
    )
    # Optional: Sadece doldurulursa doğrulanır. Boş bırakılabilir.
    password = PasswordField(
        "Yeni Şifre", 
        validators=[Optional(), Length(min=8, message="Yeni şifreniz en az 8 karakter olmalıdır.")]
    )
    confirm_password = PasswordField(
        "Yeni Şifreyi Onayla", 
        validators=[Optional(), EqualTo("password", message=MSG_PASSWORDS_MATCH)]
    )
    submit = SubmitField("Bilgileri Güncelle")

class RequestResetForm(FlaskForm):
    """Şifre sıfırlama linki istemek için kullanılan form."""
    email = StringField(
        "E-posta Adresiniz",
        validators=[DataRequired(MSG_REQUIRED), Email(message=MSG_EMAIL)]
    )
    submit = SubmitField("Sıfırlama Linki Gönder")


class ResetPasswordForm(FlaskForm):
    """Yeni şifreyi belirlemek için kullanılan form."""
    password = PasswordField(
        "Yeni Şifre",
        validators=[DataRequired(MSG_REQUIRED), Length(min=8, message="Şifreniz en az 8 karakter olmalıdır.")]
    )
    confirm_password = PasswordField(
        "Yeni Şifreyi Onayla",
        validators=[DataRequired(MSG_REQUIRED), EqualTo('password', message=MSG_PASSWORDS_MATCH)]
    )
    submit = SubmitField("Şifreyi Güncelle")

class DeleteAccountForm(FlaskForm):
    """Hesap silme onayı için şifre doğrulama formu."""
    password = PasswordField(
        "Mevcut Şifreniz",
        validators=[DataRequired(MSG_REQUIRED)]
    )
    submit = SubmitField("Hesabımı Kalıcı Olarak Sil")
    
class RequestAccountDeletionForm(FlaskForm):
    """Hesap silme linki istemek için kullanılan form."""
    email = StringField(
        "Sisteme Kayıtlı E-posta Adresiniz",
        validators=[DataRequired(MSG_REQUIRED), Email(message=MSG_EMAIL)]
    )
    submit = SubmitField("Hesap Silme Linki Gönder")