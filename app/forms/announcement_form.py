from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Length

class AnnouncementForm(FlaskForm):
    title = StringField('Başlık', validators=[DataRequired(), Length(max=200)])
    content = TextAreaField('İçerik', validators=[DataRequired()])
    submit = SubmitField('Duyuru Ekle')
