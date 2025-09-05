from flask import Blueprint, render_template, abort
from app.models import Post

# Yeni blog blueprint'ini oluşturuyoruz
blog_bp = Blueprint('blog', __name__, url_prefix='/blog')

@blog_bp.route('/')
def index():
    """
    Tüm yayınlanmış blog yazılarını, en yeniden eskiye doğru listeleyen
    ana blog sayfasını oluşturur.
    """
    # Sadece is_published=True olan yazıları alıyoruz
    posts = Post.query.filter_by(is_published=True).order_by(Post.created_at.desc()).all()
    return render_template('blog/blog_index.html', posts=posts, title="Blog")

@blog_bp.route('/<slug>')
def view_post(slug):
    """
    Belirli bir blog yazısını URL uzantısına (slug) göre bulur ve gösterir.
    """
    post = Post.query.filter_by(slug=slug, is_published=True).first()
    
    # Eğer yazı bulunamazsa veya henüz yayınlanmamışsa, 404 hatası ver.
    if not post:
        abort(404)
        
    return render_template('blog/view_post.html', post=post, title=post.title)
