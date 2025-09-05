# admin_forms.py içine eklenebilir
from flask_wtf import FlaskForm
from wtforms import StringField, DecimalField, IntegerField, SubmitField, BooleanField
from wtforms.validators import DataRequired, NumberRange

class RecurringExpenseForm(FlaskForm):
    description = StringField("Açıklama", validators=[DataRequired()])
    amount = DecimalField("Tutar", validators=[DataRequired(), NumberRange(min=0)])
    day_of_month = IntegerField("Ayın Hangi Günü Oluşturulsun?", 
                                validators=[DataRequired(), NumberRange(min=1, max=28, message="Lütfen 1 ile 28 arasında bir gün girin.")])
    is_active = BooleanField("Aktif", default=True)
    submit = SubmitField("Kaydet")