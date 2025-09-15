from __future__ import annotations
import os, io, re, base64, sqlite3, uuid, csv
from datetime import datetime

from flask import Flask, request, redirect, url_for, send_file, abort, render_template, flash, session, make_response
from PIL import Image, ImageDraw, ImageFont
import qrcode
import qrcode.constants
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.exceptions import RequestEntityTooLarge

APP_NAME = "Adeseun Ogundoyin Polytechnic Eruwa – Computerized Identity Card Using QR Code"
SCHOOL_NAME = "ADESEUN OGUNDOYIN POLYTECHNIC ERUWA"
SCHOOL_ADDRESS = "P.M.B. 1015, ERUWA, OYO STATE, NIGERIA"
SCHOOL_LOGO = os.path.join("assets", "aop_logo.png")

DB_PATH = os.path.join("data", "app.db")
UPLOAD_DIR = "uploads"
SIGN_DIR = "signatures"
RECEIPT_DIR = "receipts"
ASSETS_DIR = "assets"

# CR80 standard size 3.375" × 2.125" at 300 DPI
CARD_SIZE = (1012, 638)
MARGIN = 26

# ensure directories
os.makedirs("data", exist_ok=True)
for d in [UPLOAD_DIR, SIGN_DIR, RECEIPT_DIR, ASSETS_DIR]:
    os.makedirs(d, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")

# Limit upload size (MB) via env MAX_UPLOAD_MB (default 16MB)
app.config['MAX_CONTENT_LENGTH'] = int(os.environ.get("MAX_UPLOAD_MB", "16")) * 1024 * 1024

@app.errorhandler(RequestEntityTooLarge)
def handle_large(e):
    flash("Upload too large. Use camera snapshot (auto-compress) or upload smaller image.")
    return redirect(request.referrer or url_for('home'))

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT NOT NULL CHECK(role IN ('admin','student')),
    full_name TEXT,
    sex TEXT,
    dob TEXT,
    blood_group TEXT,
    course TEXT,
    reg_no TEXT UNIQUE,
    level TEXT,
    email TEXT UNIQUE,
    password_hash TEXT,
    passport_path TEXT,
    signature_path TEXT,
    receipt_path TEXT,
    is_approved INTEGER DEFAULT 0,
    id_print_count INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS print_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    printed_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id)
);
"""

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    with conn:
        conn.executescript(SCHEMA)
    conn.close()

init_db()

def login_required(role: str | None = None):
    def wrapper(fn):
        from functools import wraps
        @wraps(fn)
        def inner(*args, **kwargs):
            if not session.get("user_id"):
                return redirect(url_for("home"))
            if role and session.get("role") != role:
                flash("Access denied.")
                return redirect(url_for("home"))
            return fn(*args, **kwargs)
        return inner
    return wrapper

def load_user(user_id: int):
    conn = get_db()
    cur = conn.execute("SELECT * FROM users WHERE id=?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row

def load_font(size: int):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/Library/Fonts/Arial.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size=size)
            except Exception:
                pass
    return ImageFont.load_default()

FONT_H1 = load_font(38)
FONT_H2 = load_font(22)
FONT_MD = load_font(22)
FONT_SM = load_font(18)
FONT_XS = load_font(16)

def compose_id_card(student: sqlite3.Row) -> Image.Image:
    """
    Compose and return a PIL.Image (RGB) of the ID card at CARD_SIZE (print quality).
    Uses a QR code at bottom-right containing multi-line student data.
    """
    card = Image.new("RGBA", CARD_SIZE, "white")
    draw = ImageDraw.Draw(card)

    header_h = 118
    blue = (6, 61, 138, 255)
    gray = (246, 247, 251, 255)
    dark = (20, 20, 20, 255)

    # Header
    draw.rectangle((0, 0, CARD_SIZE[0], header_h), fill=blue)
    if os.path.exists(SCHOOL_LOGO):
        try:
            logo = Image.open(SCHOOL_LOGO).convert("RGBA").resize((96, 96), Image.LANCZOS)
            card.paste(logo, (MARGIN, int((header_h - 96) / 2)), logo)
        except Exception:
            pass

    # Titles
    draw.text((MARGIN + 110, 18), SCHOOL_NAME, font=FONT_H1, fill="white")
    draw.text((MARGIN + 110, 58), SCHOOL_ADDRESS, font=FONT_SM, fill="white")
    draw.text((MARGIN + 110, 86), "STUDENT IDENTITY CARD", font=FONT_SM, fill="white")

    # Photo area
    photo_w, photo_h = 300, 360
    px, py = MARGIN, header_h + MARGIN
    draw.rectangle((px, py, px + photo_w, py + photo_h), fill=gray)
    if student["passport_path"] and os.path.exists(student["passport_path"]):
        try:
            ph = Image.open(student["passport_path"]).convert("RGBA")
            ph = ph.resize((photo_w - 16, photo_h - 16), Image.LANCZOS)
            card.paste(ph, (px + 8, py + 8), ph)
        except Exception:
            pass

    # Details
    rx = px + photo_w + 28
    y = header_h + MARGIN
    row_gap = 34

    def row(lbl, val):
        nonlocal y
        draw.text((rx, y), f"{lbl}", font=FONT_H2, fill=(90, 90, 90))
        draw.text((rx + 190, y), f":  {val or ''}", font=FONT_MD, fill=dark)
        y += row_gap

    row("Full Name", student["full_name"])
    row("Sex", student["sex"])
    row("Date of Birth", student["dob"])
    row("Blood Group", student["blood_group"])
    row("Course", student["course"])
    row("Reg No.", student["reg_no"])
    row("Level", student["level"])

    # Signature
    draw.text((rx, y), "Sign", font=FONT_H2, fill=(90, 90, 90))
    draw.text((rx + 190, y), ":  ", font=FONT_MD, fill=dark)
    if student["signature_path"] and os.path.exists(student["signature_path"]):
        try:
            sig = Image.open(student["signature_path"]).convert("RGBA")
            sig.thumbnail((280, 80), Image.LANCZOS)
            card.paste(sig, (rx + 210, y - 6), sig)
        except Exception:
            pass
    y += row_gap + 8

    # ---------- QR Code section ----------
    # Prepare QR contents (multi-line, readable)
    qr_text = (
        f"REG:{student['reg_no'] or ''}\n"
        f"Name: {student['full_name'] or ''}\n"
        f"Course: {student['course'] or ''}\n"
        f"Level: {student['level'] or ''}\n"
        f"DOB: {student['dob'] or ''}"
    )

    qr = qrcode.QRCode(
        version=None,  # let library choose minimal version
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=6,
        border=2,
    )
    qr.add_data(qr_text)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGBA")

    # Place QR at bottom-right with a margin
    qr_size = 220
    try:
        qr_img = qr_img.resize((qr_size, qr_size), Image.LANCZOS)
    except Exception:
        pass
    panel_x = CARD_SIZE[0] - qr_size - MARGIN
    panel_y = CARD_SIZE[1] - qr_size - MARGIN
    card.paste(qr_img, (panel_x, panel_y))

    # Human-readable label below or beside it
    label = f"REG:{student['reg_no'] or ''} | {student['full_name'] or ''}"
    lw = draw.textlength(label, font=FONT_XS)
    # center label horizontally under QR if space available
    lbl_x = panel_x + int((qr_size - lw) / 2)
    lbl_y = panel_y + qr_size + 6
    # ensure label is within card bounds
    if lbl_y + 20 < CARD_SIZE[1]:
        draw.text((lbl_x, lbl_y), label, font=FONT_XS, fill=(40, 40, 40))

    return card.convert("RGB")

def save_upload_or_data(prefix: str, file_storage, data_url: str, out_dir: str) -> str | None:
    """
    Save either an uploaded file (file_storage) or a base64 data_url (string).
    Returns the saved file path or None.
    """
    path = None
    if file_storage and getattr(file_storage, 'filename', ''):
        ext = os.path.splitext(file_storage.filename)[1].lower()
        if ext not in [".png", ".jpg", ".jpeg"]:
            raise ValueError("Only PNG/JPG allowed")
        fname = f"{prefix}_{uuid.uuid4().hex}{ext}"
        path = os.path.join(out_dir, fname)
        file_storage.save(path)
    elif data_url:
        m = re.match(r"^data:image/(png|jpeg|jpg);base64,(.+)$", data_url)
        if not m:
            raise ValueError("Invalid image data")
        ext = ".png" if m.group(1) == "png" else ".jpg"
        raw = base64.b64decode(m.group(2))
        fname = f"{prefix}_{uuid.uuid4().hex}{ext}"
        path = os.path.join(out_dir, fname)
        with open(path, 'wb') as f:
            f.write(raw)
    return path

# ---------------- Routes ----------------

@app.context_processor
def inject_globals():
    return dict(app_name=APP_NAME, school_name=SCHOOL_NAME, school_address=SCHOOL_ADDRESS)

@app.route('/')
def home():
    conn = get_db()
    cur = conn.execute("SELECT COUNT(*) AS c FROM users WHERE role='admin'")
    no_admin = cur.fetchone()["c"] == 0
    conn.close()
    return render_template("home.html", logo_exists=os.path.exists(SCHOOL_LOGO), no_admin=no_admin)

@app.route('/logo')
def school_logo():
    if not os.path.exists(SCHOOL_LOGO):
        abort(404)
    return send_file(SCHOOL_LOGO)

@app.route('/login/student', methods=['GET','POST'])
def login_student():
    if request.method == 'POST':
        email = request.form.get('email','').strip().lower()
        pwd = request.form.get('password','')
        conn = get_db()
        cur = conn.execute("SELECT * FROM users WHERE role='student' AND email=?", (email,))
        row = cur.fetchone(); conn.close()
        if row and check_password_hash(row["password_hash"], pwd):
            session['user_id'] = row['id']; session['role'] = 'student'
            return redirect(url_for('student_dashboard'))
        flash('Invalid credentials')
    return render_template("login.html", title="Student Login")

@app.route('/login/admin', methods=['GET','POST'])
def login_admin():
    if request.method == 'POST':
        email = request.form.get('email','').strip().lower()
        pwd = request.form.get('password','')
        conn = get_db()
        cur = conn.execute("SELECT * FROM users WHERE role='admin' AND email=?", (email,))
        row = cur.fetchone(); conn.close()
        if row and check_password_hash(row["password_hash"], pwd):
            session['user_id'] = row['id']; session['role'] = 'admin'
            return redirect(url_for('admin_dashboard'))
        flash('Invalid credentials')
    return render_template("login.html", title="Admin Login")

@app.route('/logout')
def logout():
    session.clear(); return redirect(url_for('home'))

@app.route('/register/student', methods=['GET','POST'])
def register_student():
    if request.method == 'POST':
        f = request.form
        full_name = f.get('full_name','').strip()
        sex = f.get('sex','').strip()
        dob = f.get('dob','').strip()
        blood_group = f.get('blood_group','').strip()
        course = f.get('course','').strip()
        reg_no = f.get('reg_no','').strip().upper()
        level = f.get('level','').strip()
        email = f.get('email','').strip().lower()
        password = f.get('password','')
        try:
            signature_path = save_upload_or_data('sig', request.files.get('signature_file'), f.get('signature_data',''), SIGN_DIR)
        except Exception as e:
            flash(str(e)); return redirect(url_for('register_student'))
        try:
            passport_path = save_upload_or_data('pass', request.files.get('passport_file'), f.get('shot_data',''), UPLOAD_DIR)
        except Exception as e:
            flash(str(e)); return redirect(url_for('register_student'))
        if not passport_path:
            flash('Passport is required (upload or capture).'); return redirect(url_for('register_student'))
        if not signature_path:
            flash('Signature is required (upload or draw, then click "Use This").'); return redirect(url_for('register_student'))
        conn = get_db()
        try:
            with conn:
                conn.execute("""
                    INSERT INTO users (role, full_name, sex, dob, blood_group, course, reg_no, level, email, password_hash, passport_path, signature_path, created_at)
                    VALUES ('student',?,?,?,?,?,?,?,?,?,?,?,?)
                """, (full_name, sex, dob, blood_group, course, reg_no, level, email, generate_password_hash(password), passport_path, signature_path, datetime.utcnow().isoformat()))
        except sqlite3.IntegrityError as e:
            flash('Email or Reg No already exists.'); return redirect(url_for('register_student'))
        finally:
            conn.close()
        flash('Account created. Please login.')
        return redirect(url_for('login_student'))
    return render_template("reg_student.html")

@app.route('/register/admin', methods=['GET','POST'])
def register_admin():
    conn = get_db(); cur = conn.execute("SELECT COUNT(*) AS c FROM users WHERE role='admin'"); no_admin = cur.fetchone()['c']==0; conn.close()
    if not no_admin and session.get('role') != 'admin':
        flash('Only admin can create another admin.'); return redirect(url_for('home'))
    if request.method == 'POST':
        f = request.form
        full_name = f.get('full_name','').strip()
        email = f.get('email','').strip().lower()
        password = f.get('password','')
        conn = get_db()
        try:
            with conn:
                conn.execute("INSERT INTO users (role, full_name, email, password_hash, created_at) VALUES ('admin',?,?,?,?)",
                             (full_name, email, generate_password_hash(password), datetime.utcnow().isoformat()))
        except sqlite3.IntegrityError:
            flash('Admin with this email already exists.'); return redirect(url_for('register_admin'))
        finally:
            conn.close()
        flash('Admin created.')
        return redirect(url_for('login_admin'))
    return render_template("reg_admin.html")

@app.route('/admin/add-student', methods=['GET','POST'])
@login_required('admin')
def register_student_admin():
    if request.method == 'POST':
        f = request.form
        vals = (
            'student', f.get('full_name',''), f.get('sex',''), f.get('dob',''), f.get('blood_group',''), f.get('course',''),
            f.get('reg_no','').strip().upper(), f.get('level',''), f.get('email','').strip().lower(), generate_password_hash(f.get('password','')),
            None, None, None, 0, 0, datetime.utcnow().isoformat()
        )
        conn = get_db()
        try:
            with conn:
                conn.execute("""
                    INSERT INTO users (role, full_name, sex, dob, blood_group, course, reg_no, level, email, password_hash, passport_path, signature_path, receipt_path, is_approved, id_print_count, created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, vals)
        except sqlite3.IntegrityError:
            flash('Email or Reg No already exists.'); return redirect(url_for('register_student_admin'))
        finally:
            conn.close()
        flash('Student added.')
        return redirect(url_for('admin_dashboard'))
    return render_template("reg_student_admin.html")

@app.route('/student/dashboard')
@login_required('student')
def student_dashboard():
    me = load_user(session['user_id'])
    return render_template("student_dashboard.html", me=me)

@app.route('/student/edit', methods=['GET','POST'])
@login_required('student')
def student_edit():
    if request.method == 'POST':
        f = request.form
        conn = get_db()
        with conn:
            conn.execute("""
                UPDATE users SET full_name=?, sex=?, dob=?, blood_group=?, course=?, reg_no=?, level=? WHERE id=?
            """, (f.get('full_name'), f.get('sex'), f.get('dob'), f.get('blood_group'), f.get('course'), f.get('reg_no').strip().upper(), f.get('level'), session['user_id']))
        conn.close(); flash('Profile updated.')
        return redirect(url_for('student_dashboard'))
    me = load_user(session['user_id'])
    return render_template("student_edit.html", me=me)

@app.route('/student/uploads', methods=['GET','POST'])
@login_required('student')
def student_uploads():
    if request.method == 'POST':
        f = request.form
        passport_path = None; signature_path = None
        try:
            passport_path = save_upload_or_data('pass', request.files.get('passport_file'), f.get('shot_data',''), UPLOAD_DIR)
            signature_path = save_upload_or_data('sig', request.files.get('signature_file'), f.get('signature_data',''), SIGN_DIR)
        except Exception as e:
            flash(str(e)); return redirect(url_for('student_uploads'))
        conn = get_db();
        with conn:
            if passport_path:
                conn.execute("UPDATE users SET passport_path=? WHERE id=?", (passport_path, session['user_id']))
            if signature_path:
                conn.execute("UPDATE users SET signature_path=? WHERE id=?", (signature_path, session['user_id']))
        conn.close(); flash('Uploads updated.')
        return redirect(url_for('student_dashboard'))
    me = load_user(session['user_id'])
    return render_template("student_uploads.html", me=me)

@app.route('/student/upload-receipt', methods=['POST'])
@login_required('student')
def student_upload_receipt():
    f = request.form
    try:
        receipt_path = save_upload_or_data('receipt', request.files.get('receipt_file'), f.get('shot_data',''), RECEIPT_DIR)
    except Exception as e:
        flash(str(e)); return redirect(url_for('student_dashboard'))
    if not receipt_path:
        flash('No receipt provided.'); return redirect(url_for('student_dashboard'))
    conn = get_db();
    with conn:
        conn.execute("UPDATE users SET receipt_path=?, is_approved=0 WHERE id=?", (receipt_path, session['user_id']))
    conn.close(); flash('Receipt uploaded. Please wait for admin approval.')
    return redirect(url_for('student_dashboard'))

@app.route('/file/passport/<int:user_id>')
@login_required()
def student_passport(user_id):
    viewer = session['user_id']; role = session.get('role')
    if viewer != user_id and role != 'admin': abort(403)
    u = load_user(user_id)
    if not u or not u['passport_path'] or not os.path.exists(u['passport_path']): abort(404)
    return send_file(u['passport_path'])

@app.route('/file/receipt/<int:user_id>')
@login_required()
def student_receipt(user_id):
    viewer = session['user_id']; role = session.get('role')
    if viewer != user_id and role != 'admin': abort(403)
    u = load_user(user_id)
    if not u or not u['receipt_path'] or not os.path.exists(u['receipt_path']): abort(404)
    return send_file(u['receipt_path'])

@app.route('/student/card.png')
@login_required('student')
def student_card_png():
    me = load_user(session['user_id'])
    img = compose_id_card(me)  # full-size image (1012x638)
    # create a smaller preview for web (approximate ID-card look)
    preview_w, preview_h = 324, 204
    preview = img.resize((preview_w, preview_h), Image.LANCZOS)
    buf = io.BytesIO(); preview.save(buf, format='PNG', optimize=True); buf.seek(0)
    return send_file(buf, mimetype='image/png')

@app.route('/student/card.pdf')
@login_required('student')
def student_card_pdf():
    me = load_user(session['user_id'])
    if not me['is_approved']:
        flash('Not approved yet.'); return redirect(url_for('student_dashboard'))
    img = compose_id_card(me)  # full-size for printing
    buf = io.BytesIO(); img.save(buf, format='PDF'); buf.seek(0)
    conn = get_db();
    with conn:
        conn.execute("UPDATE users SET id_print_count=id_print_count+1 WHERE id=?", (me['id'],))
        conn.execute("INSERT INTO print_log (user_id, printed_at) VALUES (?,?)", (me['id'], datetime.utcnow().isoformat()))
    conn.close()
    return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name=f"{me['reg_no']}_ID.pdf")

@app.route('/admin/dashboard')
@login_required('admin')
def admin_dashboard():
    q = request.args.get('q','').strip()
    conn = get_db()
    if q:
        cur = conn.execute("SELECT * FROM users WHERE role='student' AND (full_name LIKE ? OR reg_no LIKE ?) ORDER BY id DESC", (f"%{q}%", f"%{q}%"))
    else:
        cur = conn.execute("SELECT * FROM users WHERE role='student' ORDER BY id DESC")
    students = cur.fetchall()
    cur = conn.execute("SELECT COUNT(*) AS c FROM users WHERE role='student'"); total = cur.fetchone()['c']
    cur = conn.execute("SELECT COUNT(*) AS c FROM users WHERE role='student' AND is_approved=1"); approved = cur.fetchone()['c']
    cur = conn.execute("SELECT COUNT(*) AS c FROM users WHERE role='student' AND is_approved=0"); pending = cur.fetchone()['c']
    cur = conn.execute("SELECT SUM(id_print_count) AS s FROM users WHERE role='student'"); prints = cur.fetchone()['s'] or 0
    conn.close()
    stats = { 'total': total, 'approved': approved, 'pending': pending, 'prints': prints }
    return render_template("admin_dashboard.html", students=students, stats=stats, q=q)

@app.route('/admin/approve/<int:user_id>/<int:val>')
@login_required('admin')
def admin_set_approval(user_id, val):
    conn = get_db();
    with conn:
        conn.execute("UPDATE users SET is_approved=? WHERE id=?", (1 if val else 0, user_id))
    conn.close();
    flash('Status updated.')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete/<int:user_id>')
@login_required('admin')
def admin_delete_user(user_id):
    if session['user_id'] == user_id:
        flash('You cannot delete your own account here.'); return redirect(url_for('admin_dashboard'))
    conn = get_db();
    with conn:
        conn.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.close(); flash('Account deleted.')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/print-id/<int:user_id>')
@login_required('admin')
def admin_student_card_pdf(user_id):
    u = load_user(user_id)
    if not u or u['role']!='student': abort(404)
    img = compose_id_card(u)
    buf = io.BytesIO(); img.save(buf, format='PDF'); buf.seek(0)
    conn = get_db();
    with conn:
        conn.execute("UPDATE users SET id_print_count=id_print_count+1 WHERE id=?", (u['id'],))
        conn.execute("INSERT INTO print_log (user_id, printed_at) VALUES (?,?)", (u['id'], datetime.utcnow().isoformat()))
    conn.close()
    return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name=f"{u['reg_no']}_ID.pdf")

@app.route('/admin/export.csv')
@login_required('admin')
def export_students_csv():
    conn = get_db(); cur = conn.execute("SELECT full_name,reg_no,course,level,sex,dob,blood_group,email,is_approved,id_print_count FROM users WHERE role='student' ORDER BY full_name")
    rows = cur.fetchall(); conn.close()
    si = io.StringIO(); w = csv.writer(si)
    w.writerow(["Full Name","Reg No","Course","Level","Sex","DOB","Blood Group","Email","Approved","Prints"])
    for r in rows:
        w.writerow([r['full_name'], r['reg_no'], r['course'], r['level'], r['sex'], r['dob'], r['blood_group'], r['email'], 'Yes' if r['is_approved'] else 'No', r['id_print_count']])
    out = make_response(si.getvalue()); out.headers['Content-Disposition']='attachment; filename=students.csv'; out.mimetype='text/csv'
    return out

@app.route('/developer')
def developer():
    return render_template("developer.html")

if __name__ == '__main__':
    app.run(debug=True)
