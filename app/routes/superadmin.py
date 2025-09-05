from functools import wraps
from flask import Blueprint, render_template, flash, redirect, url_for, request
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func, and_, or_

from app import db
from app.models import User, Apartment, Request, Expense, CommonArea
from app.forms.admin_forms import ApartmentForm, CSRFProtectForm
from app.forms.superadmin_forms import CommonAreaForm
from app.models import Block
from app.forms.superadmin_forms import BlockForm

superadmin_bp = Blueprint("superadmin", __name__, url_prefix="/superadmin")

def superadmin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'superadmin':
            flash('Bu sayfaya erişim yetkiniz yok.', 'danger')
            return redirect(url_for('resident.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# ====================================
# 📊 Süper Admin Dashboard + İstatistik
# ====================================


@superadmin_bp.route("/dashboard")
@login_required
@superadmin_required
def dashboard():
    if current_user.role != 'superadmin':
        flash('Bu sayfaya erişim yetkiniz yok.', 'danger')
        return redirect(url_for('resident.dashboard'))

    # 📊 Genel istatistikler
    stats = {
        "total_apartments": Apartment.query.count(),
        "total_users": User.query.count(),
        "total_admins": User.query.filter_by(role="admin").count(),
        "total_residents": User.query.filter_by(role="resident").count(),
    }

    # 🏢 Son 5 apartman
    recent_apartments = Apartment.query.order_by(Apartment.created_at.desc()).limit(5).all()

    # 🧠 Yönetici İstatistikleri
    admin_users = User.query.filter_by(role='admin').all()
    admin_stats = []
    for admin in admin_users:
        request_count = Request.query.filter(
            Request.created_by_id == admin.id,
            Request.reply.isnot(None)
        ).count()

        expense_count = Expense.query.filter_by(created_by_id=admin.id).count()

        admin_stats.append({
            "name": admin.name,
            "request_count": request_count,
            "expense_count": expense_count
        })

    return render_template(
        "superadmin_dashboard.html",
        user=current_user,
        stats=stats,
        recent_apartments=recent_apartments,
        admin_stats=admin_stats
    )


# ====================================
# Yeni Apartman Ekle
# ====================================
@superadmin_bp.route('/apartments/add', methods=['GET', 'POST'])
@login_required
@superadmin_required
def add_apartment():
    if current_user.role != 'superadmin':
        flash('Bu sayfaya erişim yetkiniz yok.', 'danger')
        return redirect(url_for('resident.dashboard'))

    form = ApartmentForm()
    if form.validate_on_submit():
        existing_apartment = Apartment.query.filter_by(name=form.name.data).first()
        if existing_apartment:
            flash('Bu isimde bir apartman zaten mevcut. Lütfen farklı bir isim seçin.', 'warning')
        else:
            new_apartment = Apartment(
                name=form.name.data,
                address=form.address.data
            )
            db.session.add(new_apartment)
            db.session.commit()
            flash(f"'{new_apartment.name}' apartmanı başarıyla oluşturuldu. Şimdi bu apartmana bir yönetici atayabilirsiniz.", 'success')
            return redirect(url_for('superadmin.user_management'))

    return render_template('superadmin/add_apartment.html', form=form)

# ====================================
# Kullanıcıları Listele ve Yönet
# ====================================
# superadmin.py dosyanızdaki bu fonksiyonu bulun ve değiştirin

@superadmin_bp.route('/users')
@login_required
@superadmin_required
def user_management():
    if current_user.role != 'superadmin':
        flash('Bu sayfaya erişim yetkiniz yok.', 'danger')
        return redirect(url_for('resident.dashboard'))
    
    # 1. Sayfalama ve filtreleme parametrelerini al
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search_query', '').strip()
    apartment_filter = request.args.get('apartment_filter', '')
    role_filter = request.args.get('role_filter', '')

    # 2. Arama yapılıp yapılmadığını kontrol et
    is_search_active = bool(search_query or apartment_filter or role_filter)

    # 3. Temel sorguyu oluştur (süper yönetici hariç)
    base_query = User.query.filter(User.id != current_user.id)

    if is_search_active:
        # ARAMA AKTİFSE: Gelen kriterlere göre filtrele
        if search_query:
            search_term = f"%{search_query}%"
            base_query = base_query.filter(or_(User.name.ilike(search_term), User.email.ilike(search_term)))
        if apartment_filter:
            base_query = base_query.filter(User.apartment_id == int(apartment_filter))
        if role_filter:
            base_query = base_query.filter(User.role == role_filter)
        # Arama sonuçlarını ID'ye göre sırala
        final_query = base_query.order_by(User.id.asc())
    else:
        # ARAMA AKTİF DEĞİLSE: Sadece son 20 kullanıcıyı al
        final_query = base_query.order_by(User.id.desc())

    # 4. Son sorgu üzerinde sayfalama uygula
    # Arama yoksa sadece ilk 20'yi göstermek için sayfa başına öğe sayısını 20 yapıyoruz.
    # Arama varsa, sayfa başına 25 sonuç gösteriyoruz.
    per_page = 25 if is_search_active else 20
    pagination = final_query.paginate(page=page, per_page=per_page, error_out=False)
    users_on_page = pagination.items

    # Eğer arama yapılmadıysa ve ilk sayfadaysak, sonuçları ters çevirerek eskiden yeniye sıralı gösterelim.
    if not is_search_active and page == 1:
        users_on_page.reverse()

    # Formlardaki dropdown menüleri için gerekli verileri hazırla
    apartments = Apartment.query.order_by(Apartment.name).all()
    blocks = Block.query.all()
    search_args = request.args.to_dict()
    
    return render_template('superadmin/user_management.html', 
                           users=users_on_page,        # <-- Artık 'users' yerine 'users_on_page'
                           apartments=apartments, 
                           blocks=blocks,
                           search_args=search_args,
                           pagination=pagination,      # <-- YENİ: Sayfalama nesnesi
                           is_search_active=is_search_active) # <-- YENİ: Arama durumunu bildiren bayrak
# ====================================
# Kullanıcı Güncelle
# ====================================
@superadmin_bp.route('/users/<int:user_id>/update', methods=['POST'])
@login_required
@superadmin_required
def update_user_attributes(user_id):
    if current_user.role != 'superadmin':
        flash('Bu işlemi yapma yetkiniz yok.', 'danger')
        return redirect(url_for('resident.dashboard'))

    user_to_modify = User.query.get_or_404(user_id)
    new_role = request.form.get('role')
    new_apartment_id = request.form.get('apartment_id')
    
    # YENİ: Formdan gelen blok ID'sini alıyoruz.
    new_block_id = request.form.get('block_id')

    if new_role in ['admin', 'resident']:
        user_to_modify.role = new_role
    else:
        flash('Geçersiz rol ataması.', 'danger')
        return redirect(url_for('superadmin.user_management'))

    if new_apartment_id:
        # Eğer kullanıcı farklı bir apartmana atanıyorsa, blok seçimini sıfırla.
        if user_to_modify.apartment_id != int(new_apartment_id):
            user_to_modify.block_id = None
        user_to_modify.apartment_id = int(new_apartment_id)
    else:
        flash('Lütfen kullanıcı için bir apartman seçin.', 'danger')
        return redirect(url_for('superadmin.user_management'))
    
    # YENİ: Blok ID'sini güncelliyoruz.
    # Eğer 'Blok Seçin' (değeri '0') seçilirse veya boş gelirse,
    # kullanıcının bloğunu 'yok' olarak (None) ayarlıyoruz.
    if new_block_id and new_block_id != '0':
        user_to_modify.block_id = int(new_block_id)
    else:
        user_to_modify.block_id = None
    
    db.session.commit()
    flash(f"{user_to_modify.name} kullanıcısının bilgileri başarıyla güncellendi.", 'success')

    return redirect(url_for('superadmin.user_management'))


# ====================================
# Kullanıcı Sil
# ====================================
@superadmin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
@superadmin_required
def delete_user(user_id):
    if current_user.role != 'superadmin':
        flash('Bu işlemi yapma yetkiniz yok.', 'danger')
        return redirect(url_for('resident.dashboard'))

    user_to_delete = User.query.get_or_404(user_id)

    if user_to_delete.id == current_user.id:
        flash("Kendinizi silemezsiniz!", "danger")
        return redirect(url_for('superadmin.user_management'))
    
    try:
        db.session.delete(user_to_delete)
        db.session.commit()
        flash(f"'{user_to_delete.name}' kullanıcısı başarıyla silindi.", "success")
    except IntegrityError:
        db.session.rollback()
        flash(f"'{user_to_delete.name}' kullanıcısı silinemedi. Kullanıcıya ait aidat, talep veya başka kayıtlar olduğu için bu işlem engellendi.", "danger")
    
    return redirect(url_for('superadmin.user_management'))


# ====================================
# Apartmanları Listele
# ====================================
@superadmin_bp.route('/apartments')
@login_required
@superadmin_required
def list_apartments():
    if current_user.role != 'superadmin':
        flash('Bu sayfaya erişim yetkiniz yok.', 'danger')
        return redirect(url_for('resident.dashboard'))
    
    apartments = Apartment.query.order_by(Apartment.name).all()
    return render_template('superadmin/list_apartments.html', apartments=apartments)


# ====================================
# Apartman Sil
# ====================================
@superadmin_bp.route('/apartments/<int:apartment_id>/delete', methods=['POST'])
@login_required
@superadmin_required
def delete_apartment(apartment_id):
    if current_user.role != 'superadmin':
        flash('Bu işlemi yapma yetkiniz yok.', 'danger')
        return redirect(url_for('resident.dashboard'))
    
    apartment_to_delete = Apartment.query.get_or_404(apartment_id)

    if apartment_to_delete.users.count() > 0:
        flash(f"'{apartment_to_delete.name}' silinemedi! Lütfen önce içindeki tüm kullanıcıları başka bir apartmana taşıyın veya silin.", "danger")
        return redirect(url_for('superadmin.list_apartments'))
    
    db.session.delete(apartment_to_delete)
    db.session.commit()
    flash(f"'{apartment_to_delete.name}' apartmanı başarıyla silindi.", "success")
    
    return redirect(url_for('superadmin.list_apartments'))

@superadmin_bp.route("/common-areas")
@login_required
@superadmin_required
def list_common_areas():
    """Sistemdeki tüm ortak alanları listeler."""
    form = CSRFProtectForm()
    # TÜM ortak alanları çekmek için apartment_id filtresini kaldırıyoruz.
    areas = CommonArea.query.order_by(CommonArea.name).all()

    # Şablon yolunu superadmin klasörüne yönlendiriyoruz.
    return render_template("superadmin/common_area_list.html", 
                           title="Ortak Alan Yönetimi (Tüm Apartmanlar)", 
                           areas=areas,
                           form=form)

@superadmin_bp.route("/common-areas/<int:area_id>/edit", methods=['GET', 'POST'])
@login_required
@superadmin_required
def edit_common_area(area_id):
    area = CommonArea.query.get_or_404(area_id)
    form = CommonAreaForm(obj=area)

    # --- EKSİK OLAN VE YENİ EKLENEN SATIR ---
    # Dropdown menüsünü apartman listesiyle dolduruyoruz.
    form.apartment_id.choices = [(a.id, a.name) for a in Apartment.query.order_by('name').all()]
    # --- YENİ SATIR SONU ---

    if form.validate_on_submit():
        area.name = form.name.data
        area.description = form.description.data
        area.is_active = form.is_active.data
        area.apartment_id = form.apartment_id.data # Apartmanı da güncellemeyi ekleyelim
        db.session.commit()

        flash(f"'{area.name}' adlı ortak alan başarıyla güncellendi.", "success")
        return redirect(url_for('superadmin.list_common_areas'))

    return render_template("superadmin/common_area_form.html",
                           title="Ortak Alanı Düzenle",
                           form=form)

@superadmin_bp.route("/common-areas/<int:area_id>/delete", methods=['POST'])
@login_required
@superadmin_required
def delete_common_area(area_id):
    """Belirli bir ortak alanı siler."""
    area = CommonArea.query.get_or_404(area_id)

    # Superadmin her alanı silebileceği için GÜVENLİK KONTROLÜNÜ KALDIRIYORUZ.
    
    area_name = area.name
    db.session.delete(area)
    db.session.commit()

    flash(f"'{area_name}' adlı ortak alan kalıcı olarak silindi.", "success")
    # Yönlendirmeyi 'superadmin' blueprint'ine göre düzeltiyoruz.
    return redirect(url_for('superadmin.list_common_areas'))

@superadmin_bp.route("/common-areas/add", methods=['GET', 'POST'])
@login_required
@superadmin_required
def add_common_area():
    """Yeni bir ortak alan oluşturur."""
    form = CommonAreaForm()
    
    # Superadmin'in apartman seçebilmesi için forma apartman listesini ekliyoruz.
    form.apartment_id.choices = [(a.id, a.name) for a in Apartment.query.order_by('name').all()]

    if form.validate_on_submit():
        new_area = CommonArea(
            name=form.name.data,
            description=form.description.data,
            is_active=form.is_active.data,
            apartment_id=form.apartment_id.data
        )
        db.session.add(new_area)
        db.session.commit()
        flash(f"'{new_area.name}' adlı ortak alan başarıyla oluşturuldu.", "success")
        return redirect(url_for('superadmin.list_common_areas'))
        
    return render_template("superadmin/common_area_form.html", 
                           title="Yeni Ortak Alan Ekle", 
                           form=form)

@superadmin_bp.route("/apartments/<int:apartment_id>")
@login_required
@superadmin_required
def apartment_details(apartment_id):
    """Belirli bir apartmanın detaylarını gösterir."""
    apartment = Apartment.query.get_or_404(apartment_id)
    # Bu apartmana ait sakinleri ve ortak alanları da sayfada göstermek için çekiyoruz.
    residents = User.query.filter_by(apartment_id=apartment.id).all()
    common_areas = CommonArea.query.filter_by(apartment_id=apartment.id).all()

    # Bu bilgilerle bir detay sayfası render ediyoruz.
    return render_template('superadmin/apartment_details.html',
                           title=f"{apartment.name} Detayları",
                           apartment=apartment,
                           residents=residents,
                           common_areas=common_areas)

# ====================================
# BLOK YÖNETİMİ
# ====================================
@superadmin_bp.route('/blocks', methods=['GET', 'POST'])
@login_required
@superadmin_required
def manage_blocks():
    """Yeni blok ekleme ve mevcut blokları listeleme sayfasını yönetir."""
    form = BlockForm()
    # Silme butonları için CSRF koruması
    csrf_form = CSRFProtectForm()
    
    # Formdaki 'Apartman/Site' dropdown menüsünü dolduruyoruz.
    form.apartment_id.choices = [(a.id, a.name) for a in Apartment.query.order_by('name').all()]
    form.apartment_id.choices.insert(0, (0, '-- Apartman Seçin --'))

    if form.validate_on_submit():
        # Aynı apartman içinde aynı isimde başka bir blok var mı diye kontrol et
        existing_block = Block.query.filter_by(name=form.name.data, apartment_id=form.apartment_id.data).first()
        if existing_block:
            flash(f"'{existing_block.apartment.name}' sitesinde bu isimde bir blok zaten mevcut.", 'warning')
        else:
            new_block = Block(name=form.name.data, apartment_id=form.apartment_id.data)
            db.session.add(new_block)
            db.session.commit()
            flash(f"'{new_block.name}' bloğu başarıyla oluşturuldu.", 'success')
            return redirect(url_for('superadmin.manage_blocks'))

    # Tüm blokları, bağlı oldukları apartman bilgisiyle birlikte çekiyoruz.
    blocks = Block.query.join(Apartment).order_by(Apartment.name, Block.name).all()
    
    return render_template('superadmin/manage_blocks.html', 
                           title="Blok Yönetimi",
                           form=form, 
                           csrf_form=csrf_form,
                           blocks=blocks)


@superadmin_bp.route('/blocks/<int:block_id>/delete', methods=['POST'])
@login_required
@superadmin_required
def delete_block(block_id):
    """Belirli bir bloğu siler."""
    block_to_delete = Block.query.get_or_404(block_id)
    
    # ÖNEMLİ KONTROL: Silinmek istenen bloğa kayıtlı kullanıcı var mı?
    if block_to_delete.users.count() > 0:
        flash(f"'{block_to_delete.name}' bloğu silinemedi! Bu bloğa kayıtlı {block_to_delete.users.count()} kullanıcı bulunmaktadır. Lütfen önce kullanıcıları başka bir bloğa taşıyın veya silin.", 'danger')
        return redirect(url_for('superadmin.manage_blocks'))

    block_name = block_to_delete.name
    db.session.delete(block_to_delete)
    db.session.commit()
    flash(f"'{block_name}' bloğu başarıyla silindi.", 'success')
    return redirect(url_for('superadmin.manage_blocks'))