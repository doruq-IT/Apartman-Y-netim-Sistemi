from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import SubmitField
from wtforms.validators import DataRequired # DataRequired, FileRequired'a göre daha standarttır

class ReceiptUploadForm(FlaskForm):
    file = FileField("Makbuz Dosyası", validators=[
        # FileRequired yerine DataRequired kullanmak daha yaygındır ve aynı işi görür
        DataRequired(message="Lütfen bir dosya seçin."), 
        FileAllowed(['pdf', 'png', 'jpg', 'jpeg'], "Sadece resim (PNG, JPG) veya PDF dosyaları kabul edilir.")
    ])
    submit = SubmitField("Makbuzu Yükle")