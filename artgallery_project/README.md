# 🖼 ArtGallery — Flask Image Gallery

Dark-themed image-sharing platform built with Flask + SQLite.

---

## ⚡ Быстрый старт (локально)

```bash
# 1. Перейти в папку проекта
cd artgallery_project

# 2. Создать и активировать виртуальное окружение
python -m venv venv
source venv/bin/activate          # macOS / Linux
# venv\Scripts\activate           # Windows

# 3. Установить зависимости
pip install -r requirements.txt

# 4. Создать базу данных
python init_db.py

# 5. Запустить приложение
python app.py
# → Открыть http://localhost:5000
```

---

## 🚀 Деплой на Render.com

1. Создать новый репозиторий на GitHub и загрузить все файлы
2. На [render.com](https://render.com) → **New → Web Service** → подключить репозиторий
3. Настройки:
   - **Build Command**: `pip install -r requirements.txt && python init_db.py`
   - **Start Command**: `gunicorn app:app`
   - **Environment**: Python 3
4. Добавить переменную окружения:
   - `SECRET_KEY` = `<любая длинная случайная строка>`
5. Нажать **Deploy**

> ⚠️ **Важно**: SQLite хранится в ephemeral-хранилище Render — при каждом новом деплое база обнуляется.
> Для production-окружения подключите **PostgreSQL** (или используйте Render Disk для SQLite-файла).

---

## 📁 Архитектура проекта

```
artgallery_project/
├── app.py                   # Все маршруты Flask и бизнес-логика
├── init_db.py               # Скрипт инициализации SQLite
├── requirements.txt         # Python-зависимости
├── Procfile                 # Для Render / Heroku
├── gallery.db               # SQLite БД (создаётся при init)
│
├── static/
│   ├── css/style.css        # Весь CSS (тёмная тема, CSS Grid, Flexbox)
│   └── uploads/             # Загруженные изображения (UUID-имена)
│
└── templates/               # Jinja2-шаблоны (наследование от base.html)
    ├── base.html            # Navbar, flash, footer, JS
    ├── index.html           # Главная галерея + герой-секция
    ├── image_detail.html    # Страница изображения + лайки + комментарии
    ├── upload.html          # Форма загрузки с drag-and-drop
    ├── register.html        # Регистрация
    ├── login.html           # Вход
    ├── profile.html         # Личный профиль (со статистикой и удалением)
    ├── public_profile.html  # Публичный профиль другого пользователя
    └── error.html           # Страницы ошибок 404 / 500
```

### Таблицы БД

| Таблица  | Поля                                          |
|----------|-----------------------------------------------|
| users    | id, username, password_hash, created_at       |
| images   | id, user_id, title, description, filename, uploaded_at |
| comments | id, image_id, user_id, text, created_at       |
| likes    | id, image_id, user_id  *(UNIQUE вместе)*      |

---

## ✅ Функциональность

| Возможность | Реализация |
|------------|-----------|
| Регистрация / Вход | Werkzeug `generate_password_hash` / `check_password_hash` |
| Загрузка изображений | UUID-имена файлов, папка `static/uploads/` |
| Галерея с поиском | SQL LIKE по title + description |
| Лайки (toggle) | Таблица likes с UNIQUE(image_id, user_id) |
| Комментарии | Только авторизованные; автор может удалять |
| Удаление изображений | Только владелец, файл удаляется с диска |
| Профиль | Статистика лайков и работ, кнопки удаления |
| Drag & Drop | Vanilla JS в base.html |
| Адаптивный дизайн | CSS Grid + Flexbox + media queries |
