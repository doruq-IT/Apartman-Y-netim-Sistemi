from flask import Blueprint, render_template, abort, flash, redirect, url_for, request
from flask_login import login_required, current_user
from sqlalchemy import func
from app.models import Poll, PollOption, Vote, db
from app.forms.poll_forms import VoteForm
from datetime import datetime

poll_bp = Blueprint('poll', __name__)


@poll_bp.route('/polls')
@login_required
def list_polls():
    """Sakinlerin, kendi apartmanlarındaki tüm aktif anketleri göreceği sayfa. (Sayfalama Eklendi)"""
    # 1. URL'den sayfa numarasını al (?page=2 gibi). Varsayılan: 1. sayfa.
    page = request.args.get('page', 1, type=int)
    # Sayfa başına gösterilecek anket sayısı (kart yapısı için 8 veya 6 daha iyi görünebilir)
    per_page = 8 

    # 2. .all() yerine .paginate() kullanarak sadece ilgili sayfadaki anketleri çek.
    pagination = Poll.query.filter_by(
        apartment_id=current_user.apartment_id,
        is_active=True
    ).order_by(Poll.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    # 3. Şablonda gösterilecek anket listesini pagination nesnesinden al.
    polls_on_page = pagination.items

    # 4. Şablona hem anketleri, hem de sayfa linkleri için pagination nesnesini gönder.
    return render_template('polls/poll_list.html', 
                           polls=polls_on_page, 
                           pagination=pagination, # <-- YENİ EKLENDİ
                           title="Aktif Anketler")


@poll_bp.route('/poll/<int:poll_id>/vote', methods=['GET', 'POST'])
@login_required
def view_poll(poll_id):
    """Sakinin belirli bir anketi görüp oy kullanacağı sayfa."""
    poll = Poll.query.get_or_404(poll_id)
    form = VoteForm()

    if poll.apartment_id != current_user.apartment_id:
        abort(403)
    
    if not poll.is_active:
        flash("Bu anket artık oy vermeye kapalıdır.", "warning")
        return redirect(url_for('poll.poll_results', poll_id=poll.id))

    # ===== YENİ EKLENEN SÜRE KONTROLÜ =====
    # Anketin bir son kullanma tarihi var mı VE o tarih geçmiş mi diye kontrol et
    if poll.expiration_date and datetime.utcnow() > poll.expiration_date:
        flash("Bu anketin oylama süresi sona ermiştir.", "warning")
        return redirect(url_for('poll.poll_results', poll_id=poll.id))
    # ===== YENİ KOD BİTİŞİ =====

    existing_vote = Vote.query.filter_by(user_id=current_user.id, poll_id=poll.id).first()
    if existing_vote:
        flash("Bu anket için daha önce oy kullandınız. Sonuçları aşağıda görebilirsiniz.", "info")
        return redirect(url_for('poll.poll_results', poll_id=poll.id))

    form.option.choices = [(option.id, option.text) for option in poll.options]

    if form.validate_on_submit():
        # ... (fonksiyonun geri kalanı aynı)
        vote = Vote(
            user_id=current_user.id,
            poll_id=poll.id,
            option_id=form.option.data
        )
        db.session.add(vote)
        db.session.commit()
        
        flash('Oyunuz başarıyla kaydedildi. Teşekkür ederiz!', 'success')
        return redirect(url_for('poll.poll_results', poll_id=poll.id))

    return render_template('polls/view_poll.html', poll=poll, form=form, title="Oylamaya Katıl")


# --- Sonuçlar sayfası fonksiyonu (değişiklik yok) ---
@poll_bp.route('/poll/<int:poll_id>/results')
@login_required
def poll_results(poll_id):
    # ... (bu fonksiyon aynı kalıyor)
    poll = Poll.query.get_or_404(poll_id)

    if poll.apartment_id != current_user.apartment_id:
        abort(403)

    total_votes = db.session.query(func.count(Vote.id)).filter(Vote.poll_id == poll.id).scalar() or 0

    results = []
    for option in poll.options:
        vote_count_for_option = db.session.query(func.count(Vote.id)).filter(
            Vote.poll_id == poll.id,
            Vote.option_id == option.id
        ).scalar() or 0
        
        percentage = (vote_count_for_option / total_votes * 100) if total_votes > 0 else 0
        
        results.append({
            'text': option.text,
            'vote_count': vote_count_for_option,
            'percentage': round(percentage)
        })

    return render_template(
        'polls/poll_results.html', 
        poll=poll, 
        results=results, 
        total_votes=total_votes,
        title="Anket Sonuçları"
    )
