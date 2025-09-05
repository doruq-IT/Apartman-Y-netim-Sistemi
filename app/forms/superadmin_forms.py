# app/forms/superadmin_forms.py

from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectField, TextAreaField, BooleanField, IntegerField
from wtforms.validators import DataRequired, Length, NumberRange

class CommonAreaForm(FlaskForm):
    """Süper Yöneticinin ortak alan eklemesi/düzenlemesi için form."""
    apartment_id = SelectField('Apartman', coerce=int, validators=[DataRequired(message="Lütfen bir apartman seçin.")])
    name = StringField('Alan Adı', validators=[DataRequired(), Length(max=100)])
    capacity = IntegerField('Maksimum Kapasite', 
                            validators=[DataRequired(message="Kapasite boş bırakılamaz."), 
                                        NumberRange(min=1, message="Kapasite en az 1 olmalıdır.")],
                            default=1)
    description = TextAreaField('Açıklama', render_kw={"rows": 3})
    is_active = BooleanField('Aktif', default=True)
    submit = SubmitField('Kaydet')

class BlockForm(FlaskForm):
    """Süper Yöneticinin bir apartmana yeni blok eklemesi için form."""
    # Hangi apartmana ekleneceğini seçmek için bu alan gerekli.
    apartment_id = SelectField('Ait Olduğu Apartman/Site', coerce=int, validators=[DataRequired("Lütfen bir apartman seçin.")])
    name = StringField('Blok Adı', validators=[DataRequired(), Length(max=100)], render_kw={"placeholder": "Örn: A Blok, G-1 Blok..."})
    submit = SubmitField('Bloğu Kaydet')