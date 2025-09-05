from flask_wtf import FlaskForm
# DEĞİŞTİ: BooleanField ve Optional import edildi
from wtforms import DecimalField, StringField, DateField, SelectField, SubmitField, BooleanField
from wtforms.validators import DataRequired, NumberRange, Optional

class DuesForm(FlaskForm):
    # DEĞİŞTİ: Bu alan artık opsiyonel. Zorunluluk kontrolü Python tarafında yapılacak.
    user_id = SelectField("Kullanıcı", coerce=int, validators=[Optional()])
    
    # YENİ: Toplu atama için onay kutusu
    assign_to_all = BooleanField('Tüm Sakinlere Ata')
    
    amount = DecimalField("Tutar", validators=[DataRequired(), NumberRange(min=0)])
    description = StringField("Açıklama", validators=[DataRequired()])
    due_date = DateField("Son Ödeme Tarihi", validators=[DataRequired()])
    submit = SubmitField("Aidat Ekle")