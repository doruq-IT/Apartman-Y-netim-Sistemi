import os
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_from_directory, abort
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.forms.document_form import DocumentUploadForm
from app.gcs_utils import upload_to_gcs 
from app.models import db, Document

document_bp = Blueprint("document", __name__)

def get_upload_folder_path():
    """Merkezi konfigürasyondan UPLOAD_FOLDER yolunu alır."""
    # Bu fonksiyon artık bize 'C:\\Users\\...\\app\\static\\uploads' gibi mutlak bir yol verecek.
    return current_app.config['UPLOAD_FOLDER']

# YENİ upload_document FONKSİYONU
@document_bp.route('/upload_document', methods=['GET', 'POST'])
@login_required
def upload_document():
    """Kullanıcıların belgelerini Google Cloud Storage'a yüklemesini yönetir."""
    if not current_user.apartment_id:
        flash("Belge yükleyebilmek için bir apartmana kayıtlı olmalısınız.", "warning")
        return redirect(url_for('resident.dashboard'))

    form = DocumentUploadForm()
    if form.validate_on_submit():
        file = form.file.data
        
        # GCS'e yükle ve public URL'i al.
        # Dosyalar GCS'te 'documents' adlı bir klasörde saklanacak.
        file_url = upload_to_gcs(file, 'documents')

        if file_url:
            try:
                new_doc = Document(
                    user_id=current_user.id,
                    apartment_id=current_user.apartment_id,
                    filename=file_url,  # Veritabanına dosyanın GCS URL'ini kaydediyoruz
                    doc_type=form.doc_type.data
                )
                db.session.add(new_doc)
                db.session.commit()
                flash('Belgeniz başarıyla yüklendi!', 'success')
                return redirect(url_for('resident.dashboard'))
            except Exception as e:
                db.session.rollback()
                flash(f"Veritabanına kayıt sırasında bir hata oluştu: {e}", "danger")
                current_app.logger.error(f"Doküman kaydı hatası: {e}")
        else:
            flash("Bir hata oluştu, belge yüklenemedi.", "danger")

    return render_template("upload_document.html", form=form)


# YENİ download_document FONKSİYONU
@document_bp.route('/download_document/<int:document_id>')
@login_required
def download_document(document_id):
    """Kullanıcıyı GCS'teki belgenin public URL'ine yönlendirir."""
    doc = Document.query.get_or_404(document_id)

    # Güvenlik kontrolü (değişmedi)
    is_owner = (doc.user_id == current_user.id)
    is_admin = (current_user.role in ['admin', 'superadmin'] and doc.apartment_id == current_user.apartment_id)

    if not is_owner and not is_admin:
        abort(403)

    # Artık dosyayı sunucudan göndermek yerine, doğrudan GCS linkine yönlendiriyoruz.
    return redirect(doc.filename)

