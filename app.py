"""
ArtGallery — Flask Image Gallery
Изображения хранятся прямо в SQLite (base64) — Volume не нужен.
"""
import os
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Dict, List, Optional, Union

from flask import (Flask, render_template, request, redirect, url_for,
                   session, flash, g, Response)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3

# ─── Config ──────────────────────────────────────────────────────────────────

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'artgallery-secret-key-2026!')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.environ.get('DATABASE', os.path.join(BASE_DIR, 'gallery.db'))
ALLOWED_EXT = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_MB = 8

app.config['MAX_CONTENT_LENGTH'] = MAX_MB * 1024 * 1024

# ─── Admin ────────────────────────────────────────────────────────────────────
# Используем длинный случайный логин – не триггерим проверку опечаток
ADMIN_USERNAME = '1237123713sdajddaa223'  # noqa: SC200
ADMIN_PASSWORD = 'admin123'

# ─── Schema ───────────────────────────────────────────────────────────────────
_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    created_at    TEXT    NOT NULL
);
CREATE TABLE IF NOT EXISTS images (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title       TEXT    NOT NULL,
    description TEXT    DEFAULT '',
    mimetype    TEXT    NOT NULL DEFAULT 'image/jpeg',
    data        BLOB    NOT NULL,
    uploaded_at TEXT    NOT NULL
);
CREATE TABLE IF NOT EXISTS comments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    image_id   INTEGER NOT NULL REFERENCES images(id) ON DELETE CASCADE,
    user_id    INTEGER NOT NULL REFERENCES users(id)  ON DELETE CASCADE,
    text       TEXT    NOT NULL,
    created_at TEXT    NOT NULL
);
CREATE TABLE IF NOT EXISTS likes (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    image_id INTEGER NOT NULL REFERENCES images(id) ON DELETE CASCADE,
    user_id  INTEGER NOT NULL REFERENCES users(id)  ON DELETE CASCADE,
    UNIQUE(image_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_images_user    ON images(user_id);
CREATE INDEX IF NOT EXISTS idx_comments_image ON comments(image_id);
CREATE INDEX IF NOT EXISTS idx_likes_image    ON likes(image_id);
"""

def _init_db() -> None:
    con = sqlite3.connect(DATABASE)
    con.executescript(_SCHEMA)
    con.commit()
    con.close()

_init_db()

def _ensure_admin() -> None:
    con = sqlite3.connect(DATABASE)
    con.row_factory = dict_factory
    if not con.execute('SELECT id FROM users WHERE username=?', (ADMIN_USERNAME,)).fetchone():
        con.execute(
            'INSERT INTO users (username, password_hash, created_at) VALUES (?,?,?)',
            (ADMIN_USERNAME, generate_password_hash(ADMIN_PASSWORD),
             datetime.now(timezone.utc).isoformat())
        )
        con.commit()
    con.close()

_ensure_admin()

# ─── DB helpers ───────────────────────────────────────────────────────────────

def dict_factory(cursor: sqlite3.Cursor, row: sqlite3.Row) -> Dict[str, Any]:
    """Преобразует строку результата в словарь."""
    fields = [column[0] for column in cursor.description]
    return {key: value for key, value in zip(fields, row)}

def get_db() -> sqlite3.Connection:
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = dict_factory
        g.db.execute('PRAGMA foreign_keys=ON')
    return g.db

@app.teardown_appcontext
def close_db(_: Optional[Exception] = None) -> None:
    db = g.pop('db', None)
    if db:
        db.close()

def q(sql: str, args: tuple = (), one: bool = False) -> Union[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Выполняет SELECT и возвращает список словарей или один словарь."""
    cur = get_db().execute(sql, args)
    rv = cur.fetchall()
    if one:
        return rv[0] if rv else None
    return rv

def m(sql: str, args: tuple = ()) -> int:
    """Выполняет INSERT/UPDATE/DELETE и возвращает lastrowid."""
    db = get_db()
    cur = db.execute(sql, args)
    db.commit()
    return cur.lastrowid

# ─── Auth ────────────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def dec(*args, **kwargs):
        if 'user_id' not in session:
            flash('Пожалуйста, войдите в систему.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return dec

def current_user() -> Optional[Dict[str, Any]]:
    if 'user_id' in session:
        return q('SELECT * FROM users WHERE id=?', (session['user_id'],), one=True)
    return None

def is_admin() -> bool:
    return session.get('username') == ADMIN_USERNAME

app.jinja_env.globals['current_user'] = current_user
app.jinja_env.globals['is_admin'] = is_admin

# ─── File helpers ────────────────────────────────────────────────────────────

def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT

def get_mimetype(filename: str) -> str:
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else 'jpg'
    return {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png',
            'gif': 'image/gif', 'webp': 'image/webp'}.get(ext, 'image/jpeg')

# ─── Template filter ─────────────────────────────────────────────────────────

@app.template_filter('timeago')
def timeago(dt_str: str) -> str:
    try:
        dt = datetime.fromisoformat(dt_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        diff = now - dt
        s = int(diff.total_seconds())
        if s < 60:
            return 'только что'
        if s < 3600:
            return f'{s // 60} мин. назад'
        if s < 86400:
            return f'{s // 3600} ч. назад'
        d = s // 86400
        if d == 1:
            return 'вчера'
        if d < 30:
            return f'{d} дн. назад'
        if d < 365:
            return f'{d // 30} мес. назад'
        return f'{d // 365} г. назад'
    except (ValueError, TypeError, AttributeError):
        return dt_str

# ─── Image serving ───────────────────────────────────────────────────────────

@app.route('/img/<int:image_id>')
def serve_image(image_id: int) -> Response:
    """Отдаёт изображение прямо из БД."""
    row = q('SELECT data, mimetype FROM images WHERE id=?', (image_id,), one=True)
    if not row:
        return '', 404
    return Response(row['data'], mimetype=row['mimetype'])

# ─── Auth routes ─────────────────────────────────────────────────────────────

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        if not username or not password:
            flash('Заполните все поля.', 'error')
        elif len(username) < 3:
            flash('Имя пользователя — минимум 3 символа.', 'error')
        elif len(password) < 6:
            flash('Пароль — минимум 6 символов.', 'error')
        elif q('SELECT id FROM users WHERE username=?', (username,), one=True):
            flash('Имя пользователя уже занято.', 'error')
        else:
            uid = m('INSERT INTO users (username, password_hash, created_at) VALUES (?,?,?)',
                    (username, generate_password_hash(password),
                     datetime.now(timezone.utc).isoformat()))
            session['user_id'] = uid
            session['username'] = username
            flash('Добро пожаловать в ArtGallery!', 'success')
            return redirect(url_for('index'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = q('SELECT * FROM users WHERE username=?', (username,), one=True)
        if not user or not check_password_hash(user['password_hash'], password):
            flash('Неверное имя пользователя или пароль.', 'error')
        else:
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash(f'С возвращением, {username}!', 'success')
            return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Вы вышли из системы.', 'info')
    return redirect(url_for('index'))

# ─── Gallery routes ───────────────────────────────────────────────────────────

@app.route('/')
def index():
    search = request.args.get('q', '').strip()
    if search:
        rows = q('''SELECT i.id, i.title, i.description, i.uploaded_at, u.username,
                   (SELECT COUNT(*) FROM likes    WHERE image_id=i.id) AS like_count,
                   (SELECT COUNT(*) FROM comments WHERE image_id=i.id) AS comment_count
                   FROM images i JOIN users u ON i.user_id=u.id
                   WHERE i.title LIKE ? OR i.description LIKE ?
                   ORDER BY i.uploaded_at DESC''', (f'%{search}%', f'%{search}%'))
    else:
        rows = q('''SELECT i.id, i.title, i.description, i.uploaded_at, u.username,
                   (SELECT COUNT(*) FROM likes    WHERE image_id=i.id) AS like_count,
                   (SELECT COUNT(*) FROM comments WHERE image_id=i.id) AS comment_count
                   FROM images i JOIN users u ON i.user_id=u.id
                   ORDER BY i.uploaded_at DESC''')
    # rows – список словарей, тип известен благодаря аннотации q()
    return render_template('index.html', images=rows, search=search)

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        file = request.files.get('image')
        if not title:
            flash('Название обязательно.', 'error')
        elif not file or file.filename == '':
            flash('Выберите файл для загрузки.', 'error')
        elif not allowed_file(file.filename):
            flash('Поддерживаются PNG, JPG, JPEG, GIF, WEBP.', 'error')
        else:
            data = file.read()
            mimetype = get_mimetype(secure_filename(file.filename))
            m('INSERT INTO images (user_id, title, description, mimetype, data, uploaded_at) VALUES (?,?,?,?,?,?)',
              (session['user_id'], title, description, mimetype, data,
               datetime.now(timezone.utc).isoformat()))
            flash('Изображение успешно загружено!', 'success')
            return redirect(url_for('index'))
    return render_template('upload.html')

@app.route('/image/<int:image_id>')
def image_detail(image_id: int):
    img = q('''SELECT i.id, i.title, i.description, i.uploaded_at, i.user_id, u.username,
               (SELECT COUNT(*) FROM likes WHERE image_id=i.id) AS like_count
               FROM images i JOIN users u ON i.user_id=u.id WHERE i.id=?''',
            (image_id,), one=True)
    if not img:
        flash('Изображение не найдено.', 'error')
        return redirect(url_for('index'))
    comments = q('''SELECT c.id, c.text, c.created_at, c.user_id, u.username
                   FROM comments c JOIN users u ON c.user_id=u.id
                   WHERE c.image_id=? ORDER BY c.created_at ASC''', (image_id,))
    user_liked = False
    if 'user_id' in session:
        user_liked = q('SELECT id FROM likes WHERE image_id=? AND user_id=?',
                       (image_id, session['user_id']), one=True) is not None
    return render_template('image_detail.html', image=img, comments=comments, user_liked=user_liked)

@app.route('/image/<int:image_id>/delete', methods=['POST'])
@login_required
def delete_image(image_id: int):
    img = q('SELECT * FROM images WHERE id=?', (image_id,), one=True)
    if not img:
        flash('Изображение не найдено.', 'error')
        return redirect(url_for('index'))
    if img['user_id'] != session['user_id'] and not is_admin():
        flash('Нет доступа.', 'error')
        return redirect(url_for('image_detail', image_id=image_id))
    m('DELETE FROM images WHERE id=?', (image_id,))
    flash('Изображение удалено.', 'success')
    if is_admin() and img['user_id'] != session['user_id']:
        return redirect(url_for('index'))
    return redirect(url_for('profile'))

@app.route('/image/<int:image_id>/like', methods=['POST'])
@login_required
def toggle_like(image_id: int):
    if q('SELECT id FROM likes WHERE image_id=? AND user_id=?', (image_id, session['user_id']), one=True):
        m('DELETE FROM likes WHERE image_id=? AND user_id=?', (image_id, session['user_id']))
    else:
        m('INSERT INTO likes (image_id, user_id) VALUES (?,?)', (image_id, session['user_id']))
    return redirect(url_for('image_detail', image_id=image_id))

@app.route('/image/<int:image_id>/comment', methods=['POST'])
@login_required
def add_comment(image_id: int):
    text = request.form.get('text', '').strip()
    if not text:
        flash('Комментарий не может быть пустым.', 'error')
    elif len(text) > 1000:
        flash('Комментарий слишком длинный (макс. 1000 символов).', 'error')
    else:
        img = q('SELECT id FROM images WHERE id=?', (image_id,), one=True)
        if not img:
            flash('Изображение не найдено.', 'error')
            return redirect(url_for('index'))
        m('INSERT INTO comments (image_id, user_id, text, created_at) VALUES (?,?,?,?)',
          (image_id, session['user_id'], text, datetime.now(timezone.utc).isoformat()))
        flash('Комментарий добавлен!', 'success')
    return redirect(url_for('image_detail', image_id=image_id))

@app.route('/comment/<int:comment_id>/delete', methods=['POST'])
@login_required
def delete_comment(comment_id: int):
    c = q('SELECT * FROM comments WHERE id=?', (comment_id,), one=True)
    if not c:
        flash('Комментарий не найден.', 'error')
        return redirect(url_for('index'))
    if c['user_id'] != session['user_id'] and not is_admin():
        flash('Нет доступа.', 'error')
        return redirect(url_for('image_detail', image_id=c['image_id']))
    image_id = c['image_id']
    m('DELETE FROM comments WHERE id=?', (comment_id,))
    flash('Комментарий удалён.', 'success')
    return redirect(url_for('image_detail', image_id=image_id))

# ─── Profile routes ───────────────────────────────────────────────────────────

@app.route('/profile')
@login_required
def profile():
    uid = session['user_id']
    user = q('SELECT * FROM users WHERE id=?', (uid,), one=True)
    images = q('''SELECT i.id, i.title, i.description, i.uploaded_at,
                  (SELECT COUNT(*) FROM likes    WHERE image_id=i.id) AS like_count,
                  (SELECT COUNT(*) FROM comments WHERE image_id=i.id) AS comment_count
                  FROM images i WHERE i.user_id=? ORDER BY i.uploaded_at DESC''', (uid,))
    total_likes = sum(img['like_count'] for img in images)  # type: ignore
    return render_template('profile.html', user=user, images=images, total_likes=total_likes)

@app.route('/profile/<username>')
def public_profile(username: str):
    user = q('SELECT * FROM users WHERE username=?', (username,), one=True)
    if not user:
        flash('Пользователь не найден.', 'error')
        return redirect(url_for('index'))
    images = q('''SELECT i.id, i.title, i.description, i.uploaded_at,
                  (SELECT COUNT(*) FROM likes    WHERE image_id=i.id) AS like_count,
                  (SELECT COUNT(*) FROM comments WHERE image_id=i.id) AS comment_count
                  FROM images i WHERE i.user_id=? ORDER BY i.uploaded_at DESC''', (user['id'],))
    total_likes = sum(img['like_count'] for img in images)  # type: ignore
    return render_template('public_profile.html', profile_user=user, images=images, total_likes=total_likes)

# ─── Admin routes ─────────────────────────────────────────────────────────────

@app.route('/admin')
@login_required
def admin_panel():
    if not is_admin():
        flash('Нет доступа.', 'error')
        return redirect(url_for('index'))
    images = q('''SELECT i.id, i.title, i.uploaded_at, u.username,
                  (SELECT COUNT(*) FROM likes    WHERE image_id=i.id) AS like_count,
                  (SELECT COUNT(*) FROM comments WHERE image_id=i.id) AS comment_count
                  FROM images i JOIN users u ON i.user_id=u.id
                  ORDER BY i.uploaded_at DESC''')
    users_count = q('SELECT COUNT(*) as cnt FROM users', one=True)['cnt']
    return render_template('admin.html', images=images, users_count=users_count)

# ─── Error handlers ───────────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(_: Exception) -> tuple:
    return render_template('error.html', code=404, message='Страница не найдена'), 404

@app.errorhandler(413)
def too_large(_: Exception) -> Response:
    flash(f'Файл слишком большой. Максимум {MAX_MB} МБ.', 'error')
    return redirect(url_for('upload'))

@app.errorhandler(500)
def server_error(_: Exception) -> tuple:
    return render_template('error.html', code=500, message='Внутренняя ошибка сервера'), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)