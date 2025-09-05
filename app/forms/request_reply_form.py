from flask_wtf import FlaskForm
from wtforms import TextAreaField, SubmitField
from wtforms.validators import DataRequired

class RequestReplyForm(FlaskForm):
    reply = TextAreaField("Yanıt", validators=[DataRequired()])
    submit = SubmitField("Yanıtı Gönder")
