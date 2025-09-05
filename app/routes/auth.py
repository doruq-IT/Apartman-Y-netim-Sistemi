from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from app.models import User, Apartment, Block
from app.models import User, Apartment
from app.email import send_email
from urllib.parse import urlsplit
from threading import Thread
from flask_mail import Message
from app.extensions import limiter
from app.extensions import db
from app.forms.auth_forms import LoginForm, RegisterForm, ProfileEditForm
from app.forms.auth_forms import RequestResetForm, ResetPasswordForm

# Blueprint tanımı
auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute", methods=["POST"])
def login():
    """Kullanıcı giriş işlemlerini yönetir."""
    # Eğer kullanıcı zaten giriş yapmışsa, onu rolüne göre paneline yönlendir.
    if current_user.is_authenticated:
        role = current_user.role.lower()
        if role == "superadmin":
            return redirect(url_for("superadmin.dashboard"))
        elif role == "admin":
            return redirect(url_for("admin.dashboard"))
        return redirect(url_for("resident.dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and check_password_hash(user.password, form.password.data):
            
            # Önce e-posta doğrulanmış mı?
            if not user.is_email_verified:
                flash("E-posta doğrulanmamış. Aktivasyon linkini kontrol edin. Mail adresinizin Spam klasörüne de bakın.", "warning")
                return redirect(url_for("auth.login"))
            
            # Kullanıcının hesabı aktif mi diye kontrol et.
            if not user.is_active:
                flash("Hesabınız henüz yönetici tarafından onaylanmamıştır veya pasif durumdadır. Lütfen daha sonra tekrar deneyin veya yöneticinizle iletişime geçin.", "warning")
                return redirect(url_for("auth.login"))

            login_user(user, remember=form.remember.data)
            flash("Başarıyla giriş yaptınız.", "success")
            
            # GİRİŞ SONRASI YÖNLENDİRME (GÜNCELLENDİ)
            next_page = request.args.get('next')
            
            # Eğer gidilecek bir sonraki sayfa yoksa VEYA bu sayfa dış bir link ise,
            # kullanıcıyı rolüne göre normal paneline yönlendir.
            if not next_page or urlsplit(next_page).netloc != '':
                role = user.role.lower()
                if role == "superadmin":
                    return redirect(url_for("superadmin.dashboard"))
                elif role == "admin":
                    return redirect(url_for("admin.dashboard"))
                elif role == "resident":
                    return redirect(url_for("resident.dashboard"))
                else:
                    flash("Kullanıcı rolünüz tanımsız, lütfen yönetici ile iletişime geçin.", "warning")
                    return redirect(url_for("auth.login"))
            
            # Eğer güvenli bir 'next_page' varsa, kullanıcıyı oraya yönlendir.
            return redirect(next_page)

        flash("Hatalı e-posta veya şifre. Lütfen tekrar deneyin.", "danger")
        
    return render_template("login.html", form=form)

@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    """Yeni kullanıcı kayıt işlemlerini yönetir."""
    form = RegisterForm()

    apartments = Apartment.query.order_by(Apartment.name).all()
    form.apartment_id.choices = [(apt.id, apt.name) for apt in apartments]
    form.apartment_id.choices.insert(0, (0, 'Lütfen Apartman/Site Seçin'))

    blocks = Block.query.all()
    form.block_id.choices = [(0, 'Blok Seçin')] + [(b.id, b.name) for b in blocks]

    if form.validate_on_submit():
        existing_user = User.query.filter_by(email=form.email.data).first()
        if existing_user:
            form.email.errors.append("Bu e-posta adresi zaten kayıtlı. Lütfen farklı bir adres deneyin.")
        else:
            hashed_password = generate_password_hash(form.password.data)
            selected_block_id = form.block_id.data if form.block_id.data != 0 else None

            new_user = User(
                name=f"{form.first_name.data.strip()} {form.last_name.data.strip()}",
                email=form.email.data,
                phone_number=form.phone_number.data,
                password=hashed_password,
                apartment_id=form.apartment_id.data,
                block_id=selected_block_id,
                daire_no=form.daire_no.data,
                role="resident"
            )
            db.session.add(new_user)
            db.session.commit()

            # === SADECE KULLANICIYA AKTİVASYON E-POSTASI GÖNDERİLİYOR ===
            try:
                token = new_user.generate_confirmation_token()
                confirm_url = url_for("auth.confirm_email", token=token, _external=True)

                send_email(
                    to=new_user.email,
                    subject="AYS • E-posta Doğrulama",
                    template="email/welcome",
                    user=new_user,
                    confirm_url=confirm_url
                )
            except Exception as e:
                current_app.logger.error(f"Aktivasyon maili gönderilemedi: {e}")

            # YÖNETİCİ BİLDİRİM BLOĞU BURADAN SİLİNDİ

            flash("Kaydınız alındı. E-posta hesabınıza gelen doğrulama linkine tıklayın. Sonra yöneticinizin onayını bekleyeceksiniz.", "info")
            return redirect(url_for("auth.login"))

    return render_template("signup.html", form=form, blocks=blocks)

@auth_bp.route("/logout")
@login_required
def logout():
    """Kullanıcı çıkış işlemini yapar."""
    logout_user()
    flash("Başarıyla çıkış yaptınız.", "info")
    return redirect(url_for("auth.login"))

@auth_bp.route("/profile/edit", methods=["GET", "POST"])
@login_required
def edit_profile():
    """Kullanıcının kendi profilini düzenlemesini sağlar."""
    form = ProfileEditForm(obj=current_user)
    
    if form.validate_on_submit():
        current_user.name = form.name.data
        current_user.email = form.email.data
        current_user.phone_number = form.phone_number.data
        
        # Sadece yeni şifre alanı doldurulduysa şifreyi güncelle
        if form.password.data:
            current_user.password = generate_password_hash(form.password.data)
            
        db.session.commit()
        flash("Profil bilgileriniz başarıyla güncellendi.", "success")
        return redirect(url_for("resident.profile")) # Genellikle kullanıcıyı profil sayfasına geri yönlendiririz.
        
    return render_template("profile_edit.html", form=form)

@auth_bp.route("/reset_password", methods=['GET', 'POST'])
def reset_request():
    """
    Kullanıcının şifre sıfırlama linki talep ettiği adımı yönetir.
    """
    # Giriş yapmış kullanıcı bu sayfaya gelirse, paneline yönlendir.
    if current_user.is_authenticated:
        return redirect(url_for('resident.dashboard'))
    
    form = RequestResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            # Kullanıcı varsa, bir sıfırlama e-postası gönder.
            # Kullanıcı yoksa güvenlik nedeniyle bir şey söyleme.
            try:
                token = user.get_reset_token()
                send_email(
                    to=user.email,
                    subject='AYS - Şifre Sıfırlama İsteği',
                    template='email/reset_password',
                    user=user,
                    token=token
                )
            except Exception as e:
                current_app.logger.error(f"Şifre sıfırlama e-postası gönderilemedi: {e}")

        flash('Eğer girdiğiniz e-posta adresi sistemimizde kayıtlıysa, şifre sıfırlama talimatları gönderilmiştir.', 'info')
        return redirect(url_for('auth.login'))
        
    return render_template('auth/reset_request.html', title='Şifre Sıfırla', form=form)


@auth_bp.route("/reset_password/<token>", methods=['GET', 'POST'])
def reset_token(token):
    """
    E-postadaki linke tıklandığında yeni şifrenin belirlendiği adımı yönetir.
    """
    if current_user.is_authenticated:
        return redirect(url_for('resident.dashboard'))
    
    # Gelen token'ı doğrula
    user = User.verify_reset_token(token)
    if user is None:
        flash('Bu şifre sıfırlama linki geçersiz veya süresi dolmuş.', 'warning')
        return redirect(url_for('auth.reset_request'))
    
    form = ResetPasswordForm()
    if form.validate_on_submit():
        # Yeni şifreyi hash'le ve kullanıcıyı güncelle
        hashed_password = generate_password_hash(form.password.data)
        user.password = hashed_password
        db.session.commit()
        flash('Şifreniz başarıyla güncellendi! Şimdi giriş yapabilirsiniz.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_token.html', title='Yeni Şifre Belirle', form=form, token=token)

# ────────────────────────────────────────────────────────────────
@auth_bp.route("/confirm_email/<token>")
def confirm_email(token):
    """E-posta doğrulama linki buraya gelir."""
    user = User.verify_confirmation_token(token)

    if not user:
        flash("Aktivasyon linki geçersiz veya süresi dolmuş.", "warning")
        return redirect(url_for("auth.login"))

    if user.is_email_verified:
        flash("E-posta zaten doğrulanmış. Giriş yapabilirsiniz.", "info")
        return redirect(url_for("auth.login"))

    # 1) Kullanıcının e-postasını doğrula
    user.is_email_verified = True
    db.session.commit()

    # 2) YÖNETİCİYE BİLDİRİMİ BURADA GÖNDER
    try:
        # Kayıt olunan apartmanın yöneticilerini bul
        admins_to_notify = User.query.filter_by(
            apartment_id=user.apartment_id,
            role='admin'
        ).all()

        # Her yöneticiye bildirim e-postası gönder
        for admin in admins_to_notify:
            send_email(
                to=admin.email,
                subject='Yeni Kullanıcı Kaydı Onayınızı Bekliyor',
                template='email/new_user_for_approval',
                admin_name=admin.name,
                user=user,
                approval_link=url_for('admin.pending_users', _external=True)
            )
    except Exception as e:
        current_app.logger.error(f"Yöneticiye onay e-postası gönderilemedi: {e}")

    flash("E-posta adresiniz başarıyla doğrulandı! Hesabınız, yönetici onayı sonrası aktif olacaktır.", "success")
    return redirect(url_for("auth.login"))

