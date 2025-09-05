from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField, BooleanField
# YENİ: Optional validator'ı import ediyoruz
from wtforms.validators import DataRequired, Length, Optional
# YENİ: Dosya yükleme için gerekli modülleri import ediyoruz
from flask_wtf.file import FileField, FileAllowed

class PostForm(FlaskForm):
    """Yöneticinin yeni bir blog yazısı oluşturması veya düzenlemesi için form."""
    title = StringField(
        'Yazı Başlığı', 
        validators=[
            DataRequired(message="Başlık alanı zorunludur."), 
            Length(min=10, max=200, message="Başlık 10 ila 200 karakter arasında olmalıdır.")
        ],
        render_kw={"placeholder": "Dikkat çekici bir başlık girin..."}
    )
    
    # ===== YENİ EKLENEN KAPAK RESMİ ALANI =====
    image = FileField(
        'Kapak Resmi (Opsiyonel)',
        validators=[
            # Sadece belirli resim uzantılarına izin ver
            FileAllowed(['jpg', 'jpeg', 'png', 'gif'], 'Sadece resim dosyaları (jpg, png, gif) yüklenebilir!'),
            # Bu alanın boş bırakılmasına izin ver
            Optional()
        ]
    )
    # ===== YENİ ALAN BİTİŞİ =====
    
    content = TextAreaField(
        'Yazı İçeriği', 
        validators=[
            DataRequired(message="İçerik alanı boş bırakılamaz.")
        ],
        render_kw={"rows": 15, "placeholder": "Yazınızı buraya yazın..."}
    )
    
    slug = StringField(
        'URL Uzantısı (Slug)', 
        validators=[
            DataRequired(message="URL uzantısı zorunludur."), 
            Length(min=5, max=255)
        ],
        render_kw={"placeholder": "orn: apartman-yonetimi-ipuclari"}
    )
    
    is_published = BooleanField(
        'Yazıyı Şimdi Yayınla'
    )
    
    submit = SubmitField('Yazıyı Kaydet')
