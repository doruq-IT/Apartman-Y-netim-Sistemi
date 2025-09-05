from flask import Blueprint, render_template, redirect, url_for, flash, current_app, request
from flask_login import login_required, current_user
from app.forms.announcement_form import AnnouncementForm
from app.models import db, Announcement
from app.forms.admin_forms import CSRFProtectForm 
from datetime import datetime
from app.models import User
from app.email import send_email
from app.notifications import send_push_notification, send_notification_to_users
import firebase_admin
from firebase_admin import messaging

announcement_bp = Blueprint('announcement', __name__)


@announcement_bp.route('/announcements', methods=['GET'])
@login_required
def announcements():
    page = request.args.get('page', 1, type=int)
    per_page = 10 

    pagination = Announcement.query \
        .filter_by(apartment_id=current_user.apartment_id) \
        .order_by(Announcement.created_at.desc()) \
        .paginate(page=page, per_page=per_page, error_out=False)

    announcements_on_page = pagination.items

    # --- YENİ EKLENEN OKUNDU OLARAK İŞARETLEME MANTIĞI ---
    try:
        # 1. Henüz okunmamış olan duyuruları bul
        #    Kullanıcının okuduğu duyuruların ID listesini al
        read_ann_ids = {ann.id for ann in current_user.read_announcements}
        
        #    Şu anki sayfadaki duyurulardan, kullanıcının okumadıklarını filtrele
        unread_announcements = [ann for ann in announcements_on_page if ann.id not in read_ann_ids]

        # 2. Eğer okunmamış duyuru varsa, bunları okundu listesine ekle
        if unread_announcements:
            for ann in unread_announcements:
                current_user.read_announcements.append(ann)
            
            # 3. Değişiklikleri veritabanına kaydet
            db.session.commit()
            
    except Exception as e:
        # Bir hata olursa, işlemi geri al ve logla. Sayfanın çökmesini engelle.
        db.session.rollback()
        current_app.logger.error(f"Duyurular okundu olarak işaretlenirken hata: {e}")
    # --- YENİ MANTIĞIN SONU ---

    csrf_form = CSRFProtectForm()

    return render_template('announcements.html', 
                           announcements=announcements_on_page, 
                           form=csrf_form, 
                           pagination=pagination)

@announcement_bp.route('/announcements/new', methods=['GET', 'POST'])
@login_required
def create_announcement():
    if current_user.role != 'admin':
        flash('Bu sayfaya erişiminiz yok.', 'danger')
        return redirect(url_for('announcement.announcements'))

    form = AnnouncementForm()
    if form.validate_on_submit():
        if not current_user.apartment_id:
            flash("Apartman bilgisi eksik. Lütfen yöneticiyle iletişime geçin.", "danger")
            return redirect(url_for('announcement.announcements'))

        try:
            # 1. Duyuruyu veritabanına kaydet
            new_announcement = Announcement(
                title=form.title.data,
                content=form.content.data,
                created_by=current_user.id,
                apartment_id=current_user.apartment_id
            )
            db.session.add(new_announcement)
            db.session.commit()

            # 2. Apartmandaki tüm aktif sakinleri bul
            residents = User.query.filter_by(
                apartment_id=current_user.apartment_id,
                role='resident',
                is_active=True
            ).all()

            # 3. Her bir sakine döngü ile e-posta ve push bildirimi gönder
            for resident in residents:
                if resident.email:
                    try:
                        send_email(
                            to=resident.email,
                            subject=f"Yeni Duyuru: {new_announcement.title}",
                            template='email/new_announcement_notification',
                            announcement=new_announcement,
                            resident_name=resident.name
                        )
                    except Exception as e:
                        current_app.logger.error(f"Duyuru e-postası gönderilemedi (Kullanıcı: {resident.id}): {e}")

            # Şimdi tek seferde toplu push bildirimi gönder
            try:
                send_notification_to_users(
                    users=residents,
                    title=new_announcement.title,
                    body="Yeni bir duyuru yayınlandı. Detaylar için uygulamayı kontrol edebilirsiniz.",
                    notification_type="announcement",
                    item_id=new_announcement.id
                )
            except Exception as e:
                current_app.logger.error(f"Toplu duyuru push bildirimi gönderilemedi: {e}")

            flash(f"Duyuru başarıyla yayınlandı ve {len(residents)} sakine bildirim gönderildi.", 'success')

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Duyuru oluşturma ve bildirim gönderme sırasında hata: {e}")
            flash('Duyuru yayınlandı ancak bildirimler gönderilirken bir hata oluştu.', 'warning')

        return redirect(url_for('announcement.announcements'))

    return render_template('admin/announcement_manage.html', form=form)



# DEĞİŞTİ: Bu fonksiyon artık oluşturma/düzenleme için tasarladığımız ortak şablonu kullanıyor.
@announcement_bp.route('/announcements/edit/<int:announcement_id>', methods=['GET', 'POST'])
@login_required
def edit_announcement(announcement_id):
    if current_user.role != 'admin':
        flash('Yetkisiz erişim!', 'danger')
        return redirect(url_for('announcement.announcements'))

    announcement = Announcement.query.get_or_404(announcement_id)
    form = AnnouncementForm(obj=announcement)

    if form.validate_on_submit():
        announcement.title = form.title.data
        announcement.content = form.content.data
        db.session.commit()
        flash('Duyuru başarıyla güncellendi.', 'success')
        return redirect(url_for('announcement.announcements'))

    # 'announcement_edit.html' yerine yeni ortak formumuzu kullanıyoruz.
    return render_template('admin/announcement_manage.html', form=form, announcement=announcement)


# DEĞİŞİKLİK YOK: Bu fonksiyon olduğu gibi kalabilir.
@announcement_bp.route('/announcements/delete/<int:announcement_id>', methods=['POST'])
@login_required
def delete_announcement(announcement_id):
    if current_user.role != 'admin':
        flash("Bu işlem için yetkiniz yok.", "danger")
        return redirect(url_for("announcement.announcements"))

    announcement = Announcement.query.get_or_404(announcement_id)
    db.session.delete(announcement)
    db.session.commit()
    flash("Duyuru silindi.", "success")
    return redirect(url_for("announcement.announcements"))
