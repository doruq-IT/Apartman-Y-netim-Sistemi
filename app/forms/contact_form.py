from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Email, Length

class ContactForm(FlaskForm):
    """Herkese açık iletişim sayfası için form."""
    name = StringField(
        'Ad Soyad', 
        validators=[DataRequired(message="Lütfen adınızı ve soyadınızı girin.")]
    )
    email = StringField(
        'E-posta Adresiniz', 
        validators=[
            DataRequired(message="E-posta adresi zorunludur."), 
            Email(message="Lütfen geçerli bir e-posta adresi girin.")
        ]
    )
    subject = StringField(
        'Konu', 
        validators=[
            DataRequired(message="Lütfen bir konu belirtin."),
            Length(min=5, message="Konu en az 5 karakter olmalıdır.")
        ]
    )
    message = TextAreaField(
        'Mesajınız', 
        validators=[
            DataRequired(message="Mesaj alanı boş bırakılamaz."),
            Length(min=20, message="Mesajınız en az 20 karakter olmalıdır.")
        ]
    )
    submit = SubmitField('Mesajı Gönder')
