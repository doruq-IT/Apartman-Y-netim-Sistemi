from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField, BooleanField, IntegerField, SelectField
from wtforms.validators import DataRequired, Length, NumberRange

class CommonAreaForm(FlaskForm):
    """
    Yöneticinin yeni bir ortak alan eklemesi veya mevcut bir alanı
    güncellemesi için kullanılacak form.
    """
    name = StringField(
        'Ortak Alan Adı',
        validators=[DataRequired(message="Bu alan zorunludur."), Length(min=3, max=150)]
    )
    description = TextAreaField(
        'Açıklama (Opsiyonel)'
    )
    # is_active alanı, alanı geçici olarak devre dışı bırakmak için kullanılabilir
    is_active = BooleanField(
        'Rezervasyona Açık',
        default=True
    )
    submit = SubmitField('Kaydet')

class ReservationForm(FlaskForm):
    """
    Sakinin bir rezervasyon yaparken not eklemesi ve onaylaması için
    kullanılacak form.
    """
    num_of_people = IntegerField('Kişi Sayısı', 
                                 validators=[DataRequired(message="Lütfen kişi sayısını belirtin."), 
                                             NumberRange(min=1, message="Kişi sayısı en az 1 olmalıdır.")],
                                 default=1)
    duration = SelectField('Süre', 
                           coerce=int, 
                           choices=[
                               (1, '1 Saat'),
                               (2, '2 Saat'),
                               (3, '3 Saat'),
                               (4, '4 Saat')
                           ],
                           validators=[DataRequired(message="Lütfen bir süre seçin.")],
                           default=1)
    notes = TextAreaField(
        'Rezervasyon Notu (Opsiyonel)',
        render_kw={'rows': 3}
    )
    submit = SubmitField('Rezervasyonu Onayla')