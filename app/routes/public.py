# GÜNCELLEME: Gerekli modülleri import ediyoruz
from flask import Blueprint, render_template, request, current_app, flash, redirect, url_for, send_from_directory
from flask_login import login_required, current_user # <-- current_user buraya eklendi
from app.forms.contact_form import ContactForm
from app.email import send_email
from app.models import Post
from app.models import DynamicContent
from app.forms.auth_forms import RequestAccountDeletionForm
from app.models import User

public_bp = Blueprint('public', __name__)


@public_bp.route("/")
def index():
    """Uygulamanın ana karşılama sayfasını gösterir."""
    
    # ===== YENİ EKLENEN OTURUM KONTROLÜ =====
    # 1. Kullanıcının giriş yapıp yapmadığını kontrol et.
    if current_user.is_authenticated:
        # 2. Eğer giriş yapmışsa, rolüne göre ilgili panele yönlendir.
        role = current_user.role.lower()
        if role == "superadmin":
            return redirect(url_for("superadmin.dashboard"))
        elif role == "admin":
            return redirect(url_for("admin.dashboard"))
        else: # resident veya tanımsız diğer roller
            return redirect(url_for("resident.dashboard"))
    # ===== KONTROL SONU =====

    # 3. Eğer kullanıcı giriş yapmamışsa, herkese açık ana sayfayı göster.
    recent_posts = Post.query.filter_by(
        is_published=True
    ).order_by(Post.created_at.desc()).limit(3).all()
    
    return render_template("index.html", recent_posts=recent_posts)


@public_bp.route("/contact", methods=['GET', 'POST'])
def contact():
    """İletişim sayfasını gösterir ve form gönderimlerini işler."""
    form = ContactForm()
    if form.validate_on_submit():
        name = form.name.data
        sender_email = form.email.data
        subject = form.subject.data
        message_body = form.message.data
        
        try:
            send_email(
                to=current_app.config['ADMIN_EMAIL'],
                subject=f"AYS İletişim Formu: {subject}",
                template='email/contact_form_notification',
                name=name,
                email=sender_email,
                subject_body=subject,
                message_body=message_body
            )
            flash('Mesajınız başarıyla gönderildi. En kısa sürede size geri döneceğiz.', 'success')
        except Exception as e:
            current_app.logger.error(f"İletişim formu e-postası gönderilemedi: {e}")
            flash('Mesajınız gönderilirken bir hata oluştu. Lütfen daha sonra tekrar deneyin.', 'danger')

        return redirect(url_for('public.contact'))

    return render_template("public/contact.html", form=form)


# --- DEĞİŞEN BÖLÜM: ESKİ /about ROTASI KALDIRILDI, YENİLERİ EKLENDİ ---

@public_bp.route("/kullanim-sartlari")
def terms(): # <-- Fonksiyon adını terms_and_conditions'dan terms'e değiştirin
    """Kullanım Şartları sayfasını doğrudan gösterir."""
    return render_template("about/terms.html")

@public_bp.route("/gizlilik-politikasi")
def privacy(): # <-- Fonksiyon adını privacy_policy'den privacy'e değiştirin
    """Gizlilik Politikası sayfasını doğrudan gösterir."""
    return render_template("about/privacy.html")

@public_bp.route("/kvkk-aydinlatma-metni")
def kvkk(): # <-- Fonksiyon adını kvkk_text'ten kvkk'ya değiştirin
    """KVKK Aydınlatma Metni sayfasını doğrudan gösterir."""
    return render_template("about/kvkk.html")

@public_bp.route("/hakkimizda")
def about_us():
    """Hakkımızda sayfasını doğrudan gösterir."""
    return render_template("about/about_us.html")

@public_bp.route("/yardim")
def help(): # <-- Bu fonksiyon adını da help_page'den help'e kısaltabilirsiniz
    """Yardım sayfasını doğrudan gösterir."""
    return render_template("about/help.html")
    
# --- DEĞİŞİKLİK SONU ---


@public_bp.route('/robots.txt')
def robots_txt():
    return send_from_directory(current_app.static_folder, 'robots.txt')

@public_bp.route('/sitemap.xml')
def sitemap_xml():
    return send_from_directory(current_app.static_folder, 'sitemap.xml')

@public_bp.route("/cookie-settings")
def cookie_settings():
    """Çerez ayarları sayfasını gösterir."""
    return render_template("public/cookie_settings.html")

@public_bp.route('/rules')
@login_required
def rules():
    """Dinamik içerikleri veritabanından çeker ve kurallar sayfasını oluşturur."""
    site_rules = DynamicContent.query.filter_by(key='site_rules').first()
    pool_rules = DynamicContent.query.filter_by(key='pool_rules').first()
    return render_template('public/rules.html', 
                           title="Site ve Apartman Kuralları",
                           site_rules=site_rules,
                           pool_rules=pool_rules)

@public_bp.route('/request-account-deletion', methods=['GET', 'POST'])
def request_account_deletion():
    """
    Giriş yapmamış kullanıcılar için hesap silme talebi sayfasını yönetir.
    """
    form = RequestAccountDeletionForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower()).first()
        if user:
            # YENİ EKLENEN E-POSTA GÖNDERME MANTIĞI
            try:
                token = user.get_delete_token()
                # Not: 'resident.confirm_account_deletion' rotasını bir sonraki adımda oluşturacağız.
                delete_url = url_for('resident.confirm_account_deletion', token=token, _external=True)
                send_email(
                    to=user.email,
                    subject='Hesap Silme Talebi Onayı',
                    template='email/confirm_deletion', # Bu e-posta şablonunu birazdan oluşturacağız
                    user=user,
                    delete_url=delete_url
                )
            except Exception as e:
                current_app.logger.error(f"Hesap silme onayı e-postası gönderilemedi: {e}")

        flash('Eğer girdiğiniz e-posta adresi sistemimizde kayıtlı ise, hesap silme talimatlarını içeren bir e-posta gönderilmiştir.', 'info')
        return redirect(url_for('public.index'))

    return render_template('public/request_deletion_form.html', form=form, title="Hesap Silme Talebi")

