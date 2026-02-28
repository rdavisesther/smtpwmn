from flask import Flask, request, send_file, render_template_string, jsonify
import io
import re
import secrets
import os

app = Flask(__name__)

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

def is_email(s: str) -> bool:
    return bool(EMAIL_RE.match((s or "").strip()))

def build_eml(to_addr: str, from_name: str, from_email: str, subject: str, html: str) -> str:
    boundary = "----=_Boundary_" + secrets.token_hex(8)
    from_header = f'{from_name} <{from_email}>' if from_name else from_email

    lines = [
        f"To: {to_addr}",
        f"From: {from_header}",
        f"Subject: {subject or ''}",
        "MIME-Version: 1.0",
        f'Content-Type: multipart/alternative; boundary="{boundary}"',
        "",
        f"--{boundary}",
        'Content-Type: text/plain; charset="utf-8"',
        "Content-Transfer-Encoding: 7bit",
        "",
        "This email contains HTML content. Please view it in an HTML-capable email client.",
        "",
        f"--{boundary}",
        'Content-Type: text/html; charset="utf-8"',
        "Content-Transfer-Encoding: 7bit",
        "",
        html or "",
        "",
        f"--{boundary}--",
        ""
    ]
    return "\r\n".join(lines)

# Serve the composer.html file
with open("composer.html", "r", encoding="utf-8") as f:
    HTML_PAGE = f.read()

@app.get("/")
def index():
    return render_template_string(HTML_PAGE)

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/api/validate")
def api_validate():
    data = request.get_json(force=True, silent=True) or {}

    recipient = (data.get("recipient_email") or "").strip()
    from_email = (data.get("from_email") or "").strip()
    smtp_port = str(data.get("smtp_port") or "").strip()
    html = (data.get("html_body") or "").strip()

    errors = []
    if not is_email(recipient):
        errors.append("Recipient email is invalid.")
    if from_email and not is_email(from_email):
        errors.append("From email is invalid.")
    if smtp_port:
        try:
            p = int(smtp_port)
            if p < 1 or p > 65535:
                errors.append("SMTP port must be 1–65535.")
        except ValueError:
            errors.append("SMTP port must be a number.")
    if not html:
        errors.append("HTML body is empty.")

    return jsonify({"ok": len(errors) == 0, "errors": errors})

@app.post("/api/eml")
def api_eml():
    data = request.get_json(force=True, silent=True) or {}

    recipient = (data.get("recipient_email") or "").strip()
    from_name = (data.get("from_name") or "").strip()
    from_email = (data.get("from_email") or "").strip()
    subject = (data.get("subject") or "").strip()
    html = (data.get("html_body") or "")

    if not is_email(recipient):
        return jsonify({"error": "Invalid recipient email"}), 400
    if from_email and not is_email(from_email):
        return jsonify({"error": "Invalid from email"}), 400
    if not html.strip():
        return jsonify({"error": "Empty HTML body"}), 400

    eml_text = build_eml(recipient, from_name, from_email, subject, html)
    buf = io.BytesIO(eml_text.encode("utf-8"))

    return send_file(
        buf,
        mimetype="message/rfc822",
        as_attachment=True,
        download_name="email.eml",
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)