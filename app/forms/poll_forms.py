from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, FieldList, FormField, RadioField, DateTimeField
from wtforms.validators import DataRequired, Length, ValidationError, Optional
from datetime import datetime

class PollOptionForm(FlaskForm):
    """Anket seçenekleri için bir alt form. FieldList ile kullanılır."""
    class Meta:
        # Alt formların kendi CSRF token'ına ihtiyacı yoktur.
        csrf = False
    text = StringField('Seçenek Metni', validators=[DataRequired(message="Seçenek boş bırakılamaz."), Length(min=1, max=200)])

class PollCreateForm(FlaskForm):
    """Adminin yeni bir anket oluşturması için ana form."""
    question = StringField(
        'Anket Sorusu', 
        validators=[DataRequired(message="Anket sorusu zorunludur."), Length(min=10, max=500)],
        render_kw={"placeholder": "Örn: Dış cephe hangi renk olmalı?"}
    )
    
    # FieldList, dinamik olarak eklenebilen form alanları oluşturmamızı sağlar.
    # Yönetici, en az 2, en fazla 10 seçenek ekleyebilir.
    options = FieldList(
        FormField(PollOptionForm), 
        min_entries=2, 
        max_entries=10,
        label="Anket Seçenekleri"
    )

    # ===== YENİ EKLENEN TARİH ALANI =====
    expiration_date = DateTimeField(
        'Son Geçerlilik Tarihi (Opsiyonel)', 
        format='%Y-%m-%dT%H:%M',  # HTML'deki datetime-local input formatıyla uyumlu
        validators=[Optional()] # Bu alanın boş bırakılmasına izin verir
    )
    # ===== YENİ ALAN BİTİŞİ =====

    submit = SubmitField('Anketi Oluştur ve Yayınla')

    def validate_options(self, field):
        """Form gönderildiğinde en az iki seçeneğin dolu olduğunu doğrular."""
        # Boş seçenekleri filtreleyerek gerçekten doldurulmuş olanları say
        filled_options_count = sum(1 for option_form in field if option_form.text.data.strip())
        
        if filled_options_count < 2:
            # Bu hata, formun en üstünde genel bir hata olarak gösterilir.
            raise ValidationError('Lütfen en az iki geçerli anket seçeneği girin.')

    # ===== YENİ EKLENEN GEÇMİŞ TARİH KONTROLÜ =====
    def validate_expiration_date(self, field):
        """Son geçerlilik tarihinin geçmiş bir tarih olmadığını doğrular."""
        if field.data and field.data < datetime.utcnow():
            raise ValidationError('Son geçerlilik tarihi geçmiş bir zaman olamaz.')
    # ===== YENİ KONTROL BİTİŞİ =====

class VoteForm(FlaskForm):
    """Sakinin bir ankette oy kullanması için form."""
    # RadioField, kullanıcının seçeneklerden sadece birini seçmesini sağlar.
    # coerce=int, formdan gelen verinin bir tam sayıya dönüştürülmesini sağlar.
    option = RadioField(
        'Seçenekler', 
        validators=[DataRequired(message="Lütfen bir seçenek işaretleyin.")],
        coerce=int
    )
    submit = SubmitField('Oyumu Kullan')