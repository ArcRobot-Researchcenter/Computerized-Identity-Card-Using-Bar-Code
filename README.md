# Computerized-Identity-Card-Using-Bar-Code
A simple Flask web app for managing student ID cards. Students register, capture/upload their passport and signature, upload a fees receipt for approval, and once approved download a PDF ID card with a Code 128 barcode that encodes student details.

# ✨ Features

Student & Admin portals

Student registration & login

Capture passport via web camera (Chrome/Edge/Firefox)

Draw or upload digital signature (mouse/touch)

Upload fees receipt (camera or file)

Admin review & approval (lock/unlock printing)

ID card PDF with school header, photo, details, signature, and Code 128 barcode

Barcode content (human-readable label shown under bars):
AOP-ERUWA|REG:<reg>|NAME:<name>|COURSE:<course>|LEVEL:<level>|DOB:<dob>

Admin tools: student search, quick stats, CSV export, print on behalf of student

Clean, responsive UI (Bootstrap 5)

# 🧰 Tech Stack

Python 3.10+

Flask

SQLite (built-in DB for simplicity)

Pillow (ID/PDF generation)

python-barcode (Code 128)

Bootstrap 5

## 🚀 Getting Started
1) Setup
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

## pip install -r requirements.txt

2) Run
# optional: increase max upload size (MB)
# MAX_UPLOAD_MB=32 python app.py
python app.py

Open: http://127.0.0.1:5000

Important: Browsers require HTTPS or 127.0.0.1/localhost for camera access.

3) First Admin

On the home page, click Create First Admin (visible when no admin exists).

After that, admins can add more admins and manage students.

## 🧭 How to Use
Student

Register (fill form).

Signature: draw on canvas (or upload), then click Use This.

Passport: click Start Camera → Capture Snapshot (or upload a file).

Login → Upload Fees Receipt (camera or file).

Wait for Admin Approval. Once approved, click Download ID (PDF).

## Admin

Login → Dashboard

Search students, view receipts, Approve/Lock print access

Print ID on behalf, Export CSV, Delete accounts

Add Student / Admin from links in sidebar

# 🧾 Barcode Details

Symbology: Code 128 (horizontal, generous quiet zone)

Encoded string:
AOP-ERUWA|REG:<reg>|NAME:<name>|COURSE:<course>|LEVEL:<level>|DOB:<dob>

Tips: Scan from the PDF or screen with good lighting; keep the code flat and unobstructed.

## 🧪 Troubleshooting

Camera doesn’t start

Use http://127.0.0.1:5000
 (or serve over HTTPS).

Allow camera permission in the browser.

“Request Entity Too Large”

Images were too big. The app downsizes camera snapshots automatically.

Increase server limit if needed: MAX_UPLOAD_MB=32 python app.py.

Signature not showing

After drawing, click Use This to save it into the form before submitting.

Barcode won’t scan

Try from the PDF, avoid glare, zoom in; if needed we can bump module size.

Confirm your RegNo/Name didn’t include unusual characters.

## 🔒 Security Notes

Set a strong SECRET_KEY in your environment in production.

Run behind HTTPS (camera + cookie security).

The /uploads, /signatures, /receipts, and /data/app.db contain personal data—do not commit them.

## 🛣️ Roadmap (nice-to-haves)

QR code fallback (in addition to Code 128)

Bulk import students (CSV)

Multi-page A4 print sheet (8–10 cards per page)

Email notifications on approval

Role-based permissions per department

## 📝 License

This project is released under the MIT License. See LICENSE
.

## 🤝 Contributing

Pull requests are welcome. For major changes, open an issue first to discuss what you’d like to change.
