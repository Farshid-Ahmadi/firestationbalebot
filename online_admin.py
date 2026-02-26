# -*- coding: utf-8 -*-
import os
import sys
import signal
import sqlite3
import subprocess
from pathlib import Path
from html import escape
from flask import Flask, request, redirect, url_for, session, render_template_string, flash

from file_manager import Messages, QuickResponses, Subjects, Preferences


BASE_DIR = Path(__file__).resolve().parent
CHAT_HISTORY_DIR = BASE_DIR / "Chat History"
MAIN_PATH = BASE_DIR / "main.py"
BOT_PID_FILE = BASE_DIR / "bot_runner.pid"
BOT_LOG_FILE = BASE_DIR / "bot_runner.log"
DATABASE_PATH = BASE_DIR / "database.db"
WEB_LOGIN_TABLE = "web_admin_login_guard"

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("ADMIN_WEB_SECRET", "change-this-secret-in-production")


def _init_web_login_guard():
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS {WEB_LOGIN_TABLE}(
                client_key TEXT PRIMARY KEY,
                failed_attempts INTEGER NOT NULL DEFAULT 0,
                banned_until TIMESTAMP NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        conn.commit()


def _get_client_key() -> str:
    xff = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
    ip = xff or (request.remote_addr or "unknown")
    return f"web:{ip}"


def _get_admin_ban_hours() -> int:
    raw = Preferences().getAdminRequestBanDuration()
    try:
        hours = int(str(raw).strip())
    except (TypeError, ValueError):
        hours = 240
    return max(1, hours)


def _get_ban_info(client_key: str) -> tuple[bool, int]:
    """Returns (is_banned, minutes_left)."""
    with sqlite3.connect(DATABASE_PATH) as conn:
        row = conn.execute(
            f"""SELECT CAST((julianday(banned_until) - julianday('now')) * 24 * 60 AS INTEGER)
                FROM {WEB_LOGIN_TABLE}
                WHERE client_key = ?
                  AND banned_until IS NOT NULL
                  AND banned_until > datetime('now')""",
            (client_key,),
        ).fetchone()
    if not row:
        return False, 0
    minutes_left = max(1, int(row[0] or 0))
    return True, minutes_left


def _clear_login_guard(client_key: str):
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.execute(f"DELETE FROM {WEB_LOGIN_TABLE} WHERE client_key = ?", (client_key,))
        conn.commit()


def _register_failed_attempt(client_key: str, ban_hours: int) -> tuple[bool, int]:
    """
    Returns (banned_now, remaining_attempts_before_ban).
    Ban is applied on every 3rd failed attempt.
    """
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.execute(
            f"""INSERT INTO {WEB_LOGIN_TABLE}(client_key, failed_attempts, banned_until, updated_at)
                VALUES(?, 0, NULL, datetime('now'))
                ON CONFLICT(client_key) DO NOTHING""",
            (client_key,),
        )
        row = conn.execute(
            f"SELECT failed_attempts FROM {WEB_LOGIN_TABLE} WHERE client_key = ?",
            (client_key,),
        ).fetchone()
        current_failed = int(row[0] or 0) if row else 0
        new_failed = current_failed + 1

        if new_failed >= 3:
            conn.execute(
                f"""UPDATE {WEB_LOGIN_TABLE}
                    SET failed_attempts = 0,
                        banned_until = datetime('now', ?),
                        updated_at = datetime('now')
                    WHERE client_key = ?""",
                (f"+{ban_hours} hour", client_key),
            )
            conn.commit()
            return True, 0

        conn.execute(
            f"""UPDATE {WEB_LOGIN_TABLE}
                SET failed_attempts = ?,
                    banned_until = NULL,
                    updated_at = datetime('now')
                WHERE client_key = ?""",
            (new_failed, client_key),
        )
        conn.commit()
    return False, 3 - new_failed


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _pid_is_main_process(pid: int) -> bool:
    """Return True only if pid belongs to this project's main.py process."""
    try:
        cmdline = Path(f"/proc/{pid}/cmdline").read_text(encoding="utf-8", errors="ignore")
        return str(MAIN_PATH) in cmdline or "main.py" in cmdline
    except Exception:
        return False


def _resolve_python_executable() -> str:
    """
    Prefer current venv python so main.py runs with the same installed packages.
    Fallback to current interpreter if no venv path is available.
    """
    venv_dir = os.environ.get("VIRTUAL_ENV")
    if venv_dir:
        candidate = Path(venv_dir) / "bin" / "python"
        if candidate.exists():
            return str(candidate)
    return sys.executable


def ensure_bot_running() -> tuple[bool, str]:
    """Start main.py once (if not already alive). Returns (started_now, message)."""
    if not MAIN_PATH.exists():
        return False, "main.py پیدا نشد."

    if BOT_PID_FILE.exists():
        try:
            pid = int(BOT_PID_FILE.read_text(encoding="utf-8").strip())
            if _pid_alive(pid) and _pid_is_main_process(pid):
                return False, f"ربات در حال اجراست (PID {pid})."
        except Exception:
            pass

    # stale or missing pid file: start a new process
    try:
        python_exec = _resolve_python_executable()
        with BOT_LOG_FILE.open("a", encoding="utf-8") as lf:
            process = subprocess.Popen(
                [python_exec, "-u", str(MAIN_PATH)],
                cwd=str(BASE_DIR),
                stdout=lf,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        BOT_PID_FILE.write_text(str(process.pid), encoding="utf-8")
        return True, f"ربات اجرا شد (PID {process.pid})."
    except Exception as exc:
        return False, f"خطا در اجرای ربات: {exc}"


def split_history_entries(content: str):
    entries = []
    current = []
    for line in content.splitlines():
        if line.strip() == "----------":
            block = "\n".join(current).strip()
            if block:
                entries.append(block)
            current = []
        else:
            current.append(line)
    block = "\n".join(current).strip()
    if block:
        entries.append(block)
    return entries


BASE_HTML = """
<!doctype html>
<html lang="fa" dir="rtl">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>{{ title }}</title>
  <style>
    :root {
      --bg: #f3f5f9;
      --card: #ffffff;
      --line: #dfe4ea;
      --text: #1f2937;
      --muted: #5f6c80;
      --primary: #0f766e;
      --primary-soft: #d9f6f2;
      --danger: #b10000;
    }
    body { font-family: Tahoma, Arial, sans-serif; direction: rtl; margin: 0; color: var(--text); background: radial-gradient(circle at top left, #eef7ff 0%, var(--bg) 45%, #eef3f8 100%); }
    .wrap { max-width: 1120px; margin: 24px auto; background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 18px; box-shadow: 0 8px 28px rgba(31,41,55,.08); }
    .top { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 8px; }
    .top a { text-decoration: none; color: var(--primary); border: 1px solid #c6ece7; background: #f5fffd; padding: 6px 10px; border-radius: 999px; font-size: 14px; }
    .top a:hover { background: var(--primary-soft); }
    .card { border: 1px solid var(--line); background: #fff; border-radius: 10px; padding: 13px; margin: 10px 0; }
    input[type=text], input[type=password], input[type=number], textarea, select {
      width: 100%; box-sizing: border-box; padding: 8px; border: 1px solid #bfc9d7; border-radius: 7px;
      direction: rtl; text-align: right;
    }
    input[type=password].token { direction: ltr; text-align: left; letter-spacing: .2px; font-family: monospace; }
    textarea { min-height: 120px; }
    button { padding: 8px 12px; border: 1px solid #0d6e65; border-radius: 7px; background: #0f766e; color: #fff; cursor: pointer; }
    button:hover { background: #0a665f; }
    .row { display: grid; grid-template-columns: 170px 1fr; gap: 10px; align-items: center; margin: 8px 0; }
    .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    .muted { color: var(--muted); font-size: 13px; }
    .flash { background: #fff8d6; border: 1px solid #f1d774; padding: 10px; border-radius: 6px; margin: 10px 0; }
    .danger { color: var(--danger); }
    ul { margin: 0; padding-right: 18px; }
    ol { margin: 0; padding-right: 18px; }
    pre { white-space: pre-wrap; word-break: break-word; background: #fafafa; border: 1px solid #ddd; border-radius: 8px; padding: 10px; }
    .ml8 { margin-left: 8px; }
    .hero { border: 1px solid #b9ede7; background: linear-gradient(115deg, #f0fffb 0%, #eef8ff 100%); border-radius: 12px; padding: 14px; }
    .kpi { display: inline-block; padding: 4px 10px; border-radius: 999px; background: var(--primary-soft); border: 1px solid #b9ede7; font-size: 13px; }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="top">
      {% if logged_in %}
      <a href="{{ url_for('dashboard') }}">داشبورد</a>
      <a href="{{ url_for('messages_page') }}">پیام‌ها</a>
      <a href="{{ url_for('quick_page') }}">پاسخ سریع</a>
      <a href="{{ url_for('subjects_page') }}">موضوعات</a>
      <a href="{{ url_for('settings_page') }}">تنظیمات</a>
      <a href="{{ url_for('history_page') }}">تاریخچه چت</a>
      <a href="{{ url_for('logout') }}" class="danger">خروج</a>
      {% endif %}
    </div>

    {% with msgs = get_flashed_messages() %}
      {% if msgs %}
        {% for m in msgs %}
          <div class="flash">{{ m }}</div>
        {% endfor %}
      {% endif %}
    {% endwith %}

    {{ body|safe }}
  </div>
</body>
</html>
"""


def render_page(title: str, body: str):
    return render_template_string(BASE_HTML, title=title, body=body, logged_in=session.get("admin_ok", False))


def require_login():
    return session.get("admin_ok", False)


@app.route("/", methods=["GET", "POST"])
def login():
    prefs = Preferences()

    # try to keep bot alive every time login page is hit
    started, msg = ensure_bot_running()
    if started:
        flash(msg)

    if request.method == "POST":
        client_key = _get_client_key()
        banned, minutes_left = _get_ban_info(client_key)
        if banned:
            flash(f"ورود مدیر برای این IP موقتاً مسدود است. {minutes_left} دقیقه دیگر دوباره تلاش کنید.")
            return redirect(url_for("login"))

        pwd = (request.form.get("password") or "").strip()
        if pwd == prefs.getAdminPassword():
            _clear_login_guard(client_key)
            session["admin_ok"] = True
            return redirect(url_for("dashboard"))

        banned_now, remaining = _register_failed_attempt(client_key, _get_admin_ban_hours())
        if banned_now:
            flash("به‌دلیل چند بار ورود رمز اشتباه، دسترسی شما موقتاً مسدود شد.")
        else:
            flash(f"رمز عبور اشتباه است. {remaining} تلاش دیگر باقی مانده است.")

    if session.get("admin_ok"):
        return redirect(url_for("dashboard"))

    body = """
    <h2>ورود مدیریت</h2>
    <form method="post" class="card">
      <div class="row"><label>رمز عبور</label><input type="password" name="password" required></div>
      <button type="submit">ورود</button>
    </form>
    """
    return render_page("ورود", body)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
def dashboard():
    if not require_login():
        return redirect(url_for("login"))

    _, bot_msg = ensure_bot_running()
    p = Preferences()
    body = f"""
    <h2>مدیریت آنلاین ربات</h2>
    <div class="hero">
      <div><b>وضعیت ربات:</b> {escape(bot_msg)}</div>
      <div class="muted" style="margin-top:8px;">
        <span class="kpi">دستور تعیین مقصد: {escape(p.getSetTargetCommand())}</span>
      </div>
    </div>
    <div class="card">
      <h3>راهنمای راه‌اندازی و استفاده</h3>
      <ol>
        <li>ابتدا ربات را در پیام‌رسان بله بسازید و توکن آن (`atkn`) را در بخش تنظیمات ثبت کنید.</li>
        <li>ربات را به گروه مقصد اضافه کنید.</li>
        <li>در همان گروه، دستور «{escape(p.getSetTargetCommand())}» را برای ربات ارسال کنید تا گروه مقصد ثبت شود.</li>
        <li>کاربران گزارش را به ربات می‌فرستند و ربات آن را به گروه مقصد اعلان می‌کند.</li>
        <li>برای ورود به بخش مدیریت، از رمز تعریف‌شده در تنظیمات استفاده کنید.</li>
      </ol>
    </div>
    <div class="card">
      <ul>
        <li><a href="/messages">ویرایش پیام‌ها</a></li>
        <li><a href="/quick">ویرایش پاسخ‌های سریع</a></li>
        <li><a href="/subjects">ویرایش موضوعات و متن‌های آماده</a></li>
        <li><a href="/settings">ویرایش تنظیمات</a></li>
        <li><a href="/history">مشاهده تاریخچه گفتگو</a></li>
      </ul>
    </div>
    """
    return render_page("داشبورد", body)


@app.route("/messages", methods=["GET", "POST"])
def messages_page():
    if not require_login():
        return redirect(url_for("login"))

    mgr = Messages()
    keys = sorted(mgr.getAllMessages().keys())
    key = request.args.get("key") or (keys[0] if keys else "")

    if request.method == "POST":
        key = request.form.get("key", "")
        value = request.form.get("value", "")
        if key:
            mgr.set(key, value)
            flash("پیام ذخیره شد.")
        return redirect(url_for("messages_page", key=key))

    options = "".join([
        f'<option value="{escape(k)}" {"selected" if k == key else ""}>{escape(k)}</option>' for k in keys
    ])
    value = mgr.get(key) if key else ""

    body = f"""
    <h2>پیام‌ها</h2>
    <form method="get" class="card">
      <div class="row"><label>کلید پیام</label><select name="key" onchange="this.form.submit()">{options}</select></div>
    </form>
    <form method="post" class="card">
      <input type="hidden" name="key" value="{escape(key)}" />
      <div class="row"><label>متن</label><textarea name="value">{escape(value)}</textarea></div>
      <button type="submit">ذخیره</button>
    </form>
    """
    return render_page("پیام‌ها", body)


@app.route("/quick", methods=["GET", "POST"])
def quick_page():
    if not require_login():
        return redirect(url_for("login"))

    q = QuickResponses()
    if request.method == "POST":
        section = request.form.get("section", "")
        action = request.form.get("action", "")
        idx = request.form.get("idx", "")
        text = (request.form.get("text") or "").strip()

        if section in {"crit", "report"}:
            if action == "add" and text:
                (q.addCriticismQuickResponse if section == "crit" else q.addReportQuickResponse)(text)
                flash("مورد جدید اضافه شد.")
            elif action == "edit" and idx and text:
                (q.setCriticismQuickResponse if section == "crit" else q.setReportQuickResponse)(idx, text)
                flash("ویرایش انجام شد.")
            elif action == "remove" and idx:
                try:
                    (q.removeCriticismQuickResponse if section == "crit" else q.removeReportQuickResponse)(idx)
                    flash("حذف انجام شد.")
                except KeyError:
                    flash("ایندکس نامعتبر است.")
            else:
                flash("ورودی نامعتبر است.")
        return redirect(url_for("quick_page"))

    crit = q.getCriticismQuickResponse()
    report = q.getReportQuickResponses()

    def section_html(title, key, items):
        lis = "".join([f"<li>{i}. {escape(v)}</li>" for i, v in enumerate(items, start=1)]) or "<li>موردی ثبت نشده است.</li>"
        return f"""
        <div class="card">
          <h3>{title}</h3><ul>{lis}</ul><hr>
          <form method="post"><input type="hidden" name="section" value="{key}">
            <div class="row"><label>افزودن متن</label><input type="text" name="text"></div>
            <button type="submit" name="action" value="add">افزودن</button>
          </form><hr>
          <form method="post"><input type="hidden" name="section" value="{key}">
            <div class="row"><label>شماره</label><input type="number" min="1" name="idx"></div>
            <div class="row"><label>متن جدید</label><input type="text" name="text"></div>
            <button type="submit" name="action" value="edit">ویرایش</button>
          </form><hr>
          <form method="post"><input type="hidden" name="section" value="{key}">
            <div class="row"><label>شماره</label><input type="number" min="1" name="idx"></div>
            <button type="submit" name="action" value="remove">حذف</button>
          </form>
        </div>
        """

    body = "<h2>پاسخ‌های سریع</h2><div class='grid2'>" + section_html("انتقاد", "crit", crit) + section_html("گزارش", "report", report) + "</div>"
    return render_page("پاسخ سریع", body)


@app.route("/subjects", methods=["GET", "POST"])
def subjects_page():
    if not require_login():
        return redirect(url_for("login"))

    s = Subjects()
    selected = request.args.get("subject")
    if not selected and len(s.keys()) > 0:
        selected = list(s.keys())[0]

    if request.method == "POST":
        action = request.form.get("action", "")
        selected = request.form.get("subject") or selected

        if action == "add_subject":
            text = (request.form.get("text") or "").strip()
            idx_raw = (request.form.get("idx") or "").strip()
            idx = int(idx_raw) if idx_raw.isdigit() else None
            if text:
                s.addSubject(text, idx)
                selected = text
                flash("موضوع اضافه شد.")

        elif action == "edit_subject":
            old = request.form.get("old_subject", "")
            new = (request.form.get("new_subject") or "").strip()
            if old and new:
                s.editSubjects(old, new)
                selected = new
                flash("موضوع ویرایش شد.")

        elif action == "remove_subject":
            old = request.form.get("old_subject", "")
            if old:
                s.removeSubject(old)
                selected = None
                flash("موضوع حذف شد.")

        elif action == "add_defined":
            subject = request.form.get("subject", "")
            text = (request.form.get("text") or "").strip()
            idx_raw = (request.form.get("idx") or "").strip()
            idx = int(idx_raw) if idx_raw.isdigit() else None
            if subject and text:
                s.addDefinedText(subject, text, idx)
                flash("متن آماده اضافه شد.")

        elif action == "edit_defined":
            subject = request.form.get("subject", "")
            idx_raw = (request.form.get("idx") or "").strip()
            text = (request.form.get("text") or "").strip()
            if subject and idx_raw.isdigit() and text:
                ok = s.editDefinedText(subject, int(idx_raw), text)
                flash("ویرایش انجام شد." if ok else "شماره معتبر نیست.")

        elif action == "remove_defined":
            subject = request.form.get("subject", "")
            idx_raw = (request.form.get("idx") or "").strip()
            if subject and idx_raw.isdigit():
                ok = s.removeDefinedText(subject, int(idx_raw))
                flash("حذف انجام شد." if ok else "شماره معتبر نیست.")

        return redirect(url_for("subjects_page", subject=selected) if selected else url_for("subjects_page"))

    subject_options = "".join([
        f'<option value="{escape(n)}" {"selected" if n == selected else ""}>{escape(n)}</option>' for n in s.keys()
    ])

    defined = s.getDefinedTexts(selected) if selected else []
    defined_list = "".join([f"<li>{i}. {escape(t)}</li>" for i, t in enumerate(defined, 1)]) or "<li>متنی ثبت نشده است.</li>"

    body = f"""
    <h2>موضوعات و متن‌های آماده</h2>
    <div class="card">
      <form method="get"><div class="row"><label>موضوع فعال</label>
      <select name="subject" onchange="this.form.submit()">{subject_options}</select></div></form>
    </div>
    <div class="grid2">
      <div class="card">
        <h3>مدیریت موضوع</h3>
        <form method="post"><input type="hidden" name="action" value="add_subject">
          <div class="row"><label>موضوع جدید</label><input type="text" name="text"></div>
          <div class="row"><label>شماره (اختیاری)</label><input type="number" min="1" name="idx"></div>
          <button type="submit">افزودن</button>
        </form><hr>
        <form method="post"><input type="hidden" name="action" value="edit_subject">
          <input type="hidden" name="old_subject" value="{escape(selected or '')}">
          <div class="row"><label>موضوع فعلی</label><input type="text" value="{escape(selected or '')}" disabled></div>
          <div class="row"><label>نام جدید</label><input type="text" name="new_subject"></div>
          <button type="submit">ویرایش</button>
        </form><hr>
        <form method="post" onsubmit="return confirm('موضوع حذف شود؟');">
          <input type="hidden" name="action" value="remove_subject">
          <input type="hidden" name="old_subject" value="{escape(selected or '')}">
          <button type="submit">حذف موضوع فعال</button>
        </form>
      </div>
      <div class="card">
        <h3>متن‌های آماده</h3>
        <ul>{defined_list}</ul><hr>
        <form method="post"><input type="hidden" name="action" value="add_defined"><input type="hidden" name="subject" value="{escape(selected or '')}">
          <div class="row"><label>متن جدید</label><input type="text" name="text"></div>
          <div class="row"><label>شماره (اختیاری)</label><input type="number" min="1" name="idx"></div>
          <button type="submit">افزودن</button>
        </form><hr>
        <form method="post"><input type="hidden" name="action" value="edit_defined"><input type="hidden" name="subject" value="{escape(selected or '')}">
          <div class="row"><label>شماره</label><input type="number" min="1" name="idx"></div>
          <div class="row"><label>متن جدید</label><input type="text" name="text"></div>
          <button type="submit">ویرایش</button>
        </form><hr>
        <form method="post"><input type="hidden" name="action" value="remove_defined"><input type="hidden" name="subject" value="{escape(selected or '')}">
          <div class="row"><label>شماره</label><input type="number" min="1" name="idx"></div>
          <button type="submit">حذف</button>
        </form>
      </div>
    </div>
    """
    return render_page("موضوعات", body)


@app.route("/settings", methods=["GET", "POST"])
def settings_page():
    if not require_login():
        return redirect(url_for("login"))

    p = Preferences()
    if request.method == "POST":
        try:
            p.setCriticismEnabled(bool(request.form.get("crit_enable")))
            p.setCriticismAnonymous(bool(request.form.get("crit_anon")))
            p.setCriticismText((request.form.get("crit_text") or "").strip())
            p.setSetTargetCommand((request.form.get("target_cmd") or "").strip())

            active_exp = int((request.form.get("active_exp") or "0").strip())
            chat_life = int((request.form.get("chat_life") or "0").strip())
            ban_hours = int((request.form.get("admin_ban") or "0").strip())
            if active_exp < 1 or chat_life < 1 or ban_hours < 1:
                raise ValueError

            p.setActiveChatExpiration(str(active_exp))
            p.setChatLifeSpan(str(chat_life))
            p.setAdminPassword((request.form.get("admin_password") or "").strip())
            p.setAdminRequestBanDuration(str(ban_hours))

            # Sensitive field: accept token exactly as entered (no trim),
            # and reject leading/trailing whitespace.
            token_raw = request.form.get("api_token") or ""
            if token_raw:
                if token_raw != token_raw.strip():
                    raise ValueError("TOKEN_WHITESPACE")
                p.setApiToken(token_raw)

            flash("تنظیمات ذخیره شد.")
        except ValueError as exc:
            if str(exc) == "TOKEN_WHITESPACE":
                flash("توکن ربات نباید در ابتدا یا انتها فاصله داشته باشد.")
            else:
                flash("مقادیر عددی نامعتبر هستند (باید >= 1 باشند).")
        except Exception:
            flash("خطا در ذخیره تنظیمات.")
        return redirect(url_for("settings_page"))

    checked_enable = "checked" if p.isCriticismEnabled() else ""
    checked_anon = "checked" if p.isCriticismAnonymous() else ""

    current_token = p.getApiToken()
    token_hint = "تنظیم نشده" if not current_token or current_token == "Write your atkn here!" else f"{current_token[:6]}...{current_token[-4:]}" if len(current_token) > 10 else "تنظیم شده"

    body = f"""
    <h2>تنظیمات</h2>
    <form method="post" class="card">
      <div class="row"><label>انتقاد فعال</label><input type="checkbox" name="crit_enable" {checked_enable}></div>
      <div class="row"><label>انتقاد ناشناس</label><input type="checkbox" name="crit_anon" {checked_anon}></div>
      <div class="row"><label>متن موضوع انتقاد</label><input type="text" name="crit_text" value="{escape(p.getCriticismText())}"></div>
      <div class="row"><label>دستور تعیین گروه</label><input type="text" name="target_cmd" value="{escape(p.getSetTargetCommand())}"></div>
      <div class="row"><label>عمر گفتگوی فعال (ساعت)</label><input type="number" min="1" name="active_exp" value="{escape(p.getActiveChatExpiration())}"></div>
      <div class="row"><label>مدت پاسخ‌گویی (ساعت)</label><input type="number" min="1" name="chat_life" value="{escape(p.getChatLifeSpan())}"></div>
      <div class="row"><label>رمز ادمین</label><input type="text" name="admin_password" value="{escape(p.getAdminPassword())}"></div>
      <div class="row"><label>محدودیت رمز اشتباه (ساعت)</label><input type="number" min="1" name="admin_ban" value="{escape(p.getAdminRequestBanDuration())}"></div>
      <div class="row"><label>توکن ربات (ATKN)</label><input class="token" type="password" name="api_token" value="" placeholder="برای عدم تغییر خالی بگذارید" autocomplete="off" spellcheck="false"></div>
      <div class="muted">وضعیت توکن فعلی: {escape(token_hint)} | توکن نباید ابتدا/انتها فاصله داشته باشد.</div>
      <button type="submit">ذخیره</button>
    </form>
    """
    return render_page("تنظیمات", body)


@app.route("/history")
def history_page():
    if not require_login():
        return redirect(url_for("login"))

    file_name = request.args.get("file", "")
    entry_raw = request.args.get("entry", "")
    entry_idx = int(entry_raw) if entry_raw.isdigit() else 1

    files = []
    if CHAT_HISTORY_DIR.exists():
        files = sorted([p for p in CHAT_HISTORY_DIR.iterdir() if p.is_file()], key=lambda p: p.stat().st_mtime, reverse=True)

    file_links = "".join([f'<li><a href="{url_for("history_page")}?file={escape(p.name)}">{escape(p.name)}</a></li>' for p in files]) or "<li>فایلی وجود ندارد.</li>"

    content_html = "<div class='muted'>یک فایل را انتخاب کنید.</div>"
    if file_name:
        target = CHAT_HISTORY_DIR / file_name
        if target.exists() and target.is_file():
            content = target.read_text(encoding="utf-8", errors="replace")
            entries = split_history_entries(content)
            if entries:
                entry_idx = max(1, min(entry_idx, len(entries)))
                nav = " ".join([f'<a class="ml8" href="{url_for("history_page")}?file={escape(file_name)}&entry={i}">{i}</a>' for i in range(1, len(entries)+1)])
                content_html = f"<div class='card'><div>پیام‌ها: {nav}</div><pre>{escape(entries[entry_idx-1])}</pre></div>"
            else:
                content_html = "<div class='card'>محتوایی پیدا نشد.</div>"
        else:
            content_html = "<div class='card danger'>فایل انتخاب‌شده وجود ندارد.</div>"

    body = f"""
    <h2>تاریخچه گفتگو</h2>
    <div class="grid2">
      <div class="card"><h3>فایل‌ها</h3><ul>{file_links}</ul></div>
      <div>{content_html}</div>
    </div>
    """
    return render_page("تاریخچه", body)


# Ensure bot is started when web app module is loaded (Passenger / WSGI).
ensure_bot_running()
_init_web_login_guard()


if __name__ == "__main__":
    ensure_bot_running()
    app.run(host="0.0.0.0", port=8000, debug=False, use_reloader=False)
