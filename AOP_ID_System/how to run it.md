# AOP ID Card System (Barcode) — v2 (fresh)

- Fixes 413 Request Entity Too Large (server limit + client compression)
- Signature pad supports mouse + touch; exports on white background
- Improved ID layout; horizontal Code 128 barcode with human-readable label
- Camera requires HTTPS or 127.0.0.1 in Chrome

Quickstart:
```
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
python app.py
# open http://127.0.0.1:5000
```
