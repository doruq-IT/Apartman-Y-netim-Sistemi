from flask_wtf import FlaskForm
# GÜNCELLENDİ: Gereksiz FileField importu kaldırıldı.
from wtforms import StringField, SubmitField
# GÜNCELLENDİ: FileField ve FileAllowed doğru yerden import ediliyor.
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms.validators import DataRequired, Length

# --- Ortak Hata Mesajları ---
MSG_REQUIRED = "Bu alan zorunludur."

class DocumentUploadForm(FlaskForm):
    """Kullanıcıların genel belge yüklemesi için form."""
    
    # GÜNCELLENDİ: SelectField, kullanıcıya esneklik sağlamak ve şablonla uyumlu olmak için StringField'e dönüştürüldü.
    doc_type = StringField(
        "Belge Türü",
        validators=[
            DataRequired(message=MSG_REQUIRED),
            Length(min=3, max=100, message="Belge türü 3 ila 100 karakter arasında olmalıdır.")
        ],
        description="Yüklenen belgenin ne olduğunu açıklayan kısa bir başlık."
    )
    
    file = FileField(
        "Belge Dosyası",
        validators=[
            # GÜNCELLENDİ: FileRequired, DataRequired'dan daha spesifiktir.
            FileRequired(message="Lütfen bir dosya seçin."),
            # GÜNCELLENDİ: HTML'deki açıklamaya uygun olarak JPG ve PNG de eklendi.
            FileAllowed(['pdf', 'png', 'jpg', 'jpeg'], 'Sadece PDF, PNG ve JPG dosyalarına izin verilmektedir!')
        ],
        description="İzin verilen dosya türleri: JPG, PNG, PDF. Maksimum boyut: 5MB."
    )
    
    submit = SubmitField("Yükle")

