# app/forms/request_form.py
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField, SelectField
from wtforms.validators import DataRequired, Length, Optional
from flask_wtf.file import FileField, FileAllowed

CATEGORY_CHOICES = [
    ("ariza", "Arıza"),
    ("bakim", "Bakım"),
    ("yeni_talep", "Yeni talep"),
    ("diger", "Diğer"),
]

PRIORITY_CHOICES = [
    ("dusuk", "Düşük"),
    ("orta", "Orta"),
    ("yuksek", "Yüksek"),
]

LOCATION_CHOICES = [
    ("asansor", "Asansör"),
    ("elektrik", "Elektrik"),
    ("su", "Su Tesisatı"),
    ("dogalgaz", "Doğalgaz / Kazan"),
    ("otopark", "Otopark"),
    ("bahce", "Bahçe / Peyzaj"),
    ("guvenlik", "Güvenlik"),
    ("merdiven", "Merdiven / Ortak Alan"),
    ("cati", "Çatı"),
    ("dis_cephe", "Dış Cephe"),
    ("oyun_alani", "Oyun Alanı"),
    ("diger", "Diğer"),
]

class RequestForm(FlaskForm):
    title = StringField("Başlık", validators=[DataRequired(), Length(max=100)])
    description = TextAreaField("Açıklama", validators=[DataRequired()])

    category = SelectField("Kategori", choices=CATEGORY_CHOICES, validators=[DataRequired()], default="yeni_talep")
    priority = SelectField("Öncelik", choices=PRIORITY_CHOICES, validators=[DataRequired()], default="orta")
    location = SelectField("Konum/Alan", choices=LOCATION_CHOICES, validators=[Optional()])
    location_other = StringField("Diğer Konum (serbest metin)", validators=[Optional(), Length(max=100)])

    # Opsiyonel ek: jpg/png/pdf, max 5MB (MAX_CONTENT_LENGTH zaten config'te)
    attachment = FileField(
        "Foto/Belge (opsiyonel)",
        validators=[Optional(), FileAllowed(["jpg", "jpeg", "png", "pdf"], "Sadece jpg, png veya pdf!")]
    )

    submit = SubmitField("Gönder")

    # "Konum = Diğer" ise location_other zorunlu olsun
    def validate(self, extra_validators=None):
        initial_ok = super().validate(extra_validators=extra_validators)
        if not initial_ok:
            return False
        if self.location.data == "diger" and not (self.location_other.data or "").strip():
            self.location_other.errors.append("Diğer seçildiğinde bu alan zorunludur.")
            return False
        return True
