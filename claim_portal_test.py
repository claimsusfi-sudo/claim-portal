from flask import Flask, render_template, request, redirect, flash, url_for, send_from_directory
import os
import uuid
import smtplib
from email.message import EmailMessage

app = Flask(__name__)
app.secret_key = "secret-key"
app.config["UPLOAD_FOLDER"] = "uploads"
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # 25 MB per request

# Ensure upload folder exists
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# =======================
# EMAIL SETTINGS
# =======================
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_USER = "claims.usfi@gmail.com"       # Your sending email
EMAIL_PASS = "wtet orlx drgb kspv"            # Your Gmail app password
RECIPIENTS = ["arthur.cuigniez@usfloors.be", "edouard.dossche@usfloors.be"]

# ------------------------------
# Serve uploaded files
# ------------------------------
@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

# ------------------------------
# Claim form route
# ------------------------------
@app.route("/", methods=["GET", "POST"])
def claim_form():
    if request.method == "POST":
        defects_selected = request.form.getlist("defects")
        issue_files = request.files.getlist("issue_photos")
        evidence_files = request.files.getlist("evidence_photos")
        external_link = request.form.get("external_link")
        link_public = request.form.get("link_public")  # 'yes' or 'no'

        # -----------------------
        # Mandatory fields
        # -----------------------
        mandatory_fields = [
            "phone", "email", "order_date", "order_size", "move_in_date",
            "subfloor_type", "area_affected", "attic_stock", "underfloor_heating"
        ]
        for field in mandatory_fields:
            if not request.form.get(field):
                flash(f"Field {field} is required.", "error")
                return redirect(request.url)

        # -----------------------
        # Check file sizes
        # -----------------------
        total_size = sum(len(f.read()) for f in issue_files + evidence_files)
        # reset file pointer
        for f in issue_files + evidence_files:
            f.seek(0)

        if total_size > app.config["MAX_CONTENT_LENGTH"]:
            if not external_link or link_public != "yes":
                flash("Total file size exceeds 25 MB. Please provide a public external link for large files.", "error")
                return redirect(request.url)
        else:
            # Save files locally
            issue_links = []
            evidence_links = []

            def save_files(file_list, target_list):
                for file in file_list:
                    if file.filename != "":
                        filename = f"{uuid.uuid4().hex}_{file.filename}"
                        file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                        file.save(file_path)
                        link = url_for('uploaded_file', filename=filename, _external=True)
                        target_list.append(link)

            save_files(issue_files, issue_links)
            save_files(evidence_files, evidence_links)

        # -----------------------
        # Send email with links
        # -----------------------
        try:
            msg = EmailMessage()
            msg['Subject'] = f'New Coretec Claim Submission'
            msg['From'] = EMAIL_USER
            msg['To'] = ", ".join(RECIPIENTS)

            body = "Coretec Claim Submission Details:\n\n"
            for key, value in request.form.items():
                body += f"{key}: {value}\n"
            body += f"Defects selected: {', '.join(defects_selected)}\n\n"

            if total_size <= app.config["MAX_CONTENT_LENGTH"]:
                if issue_files:
                    body += "Issue Photos:\n" + "\n".join(issue_links) + "\n\n"
                if evidence_files:
                    body += "Evidence Photos:\n" + "\n".join(evidence_links) + "\n\n"
            else:
                body += f"External link provided: {external_link} (Link is public: {link_public})\n"

            msg.set_content(body)

            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()
                server.login(EMAIL_USER, EMAIL_PASS)
                server.send_message(msg)

            flash("Claim submitted successfully! Email sent.", "success")
        except Exception as e:
            flash(f"Claim saved, but email failed: {e}", "error")

        return redirect(request.url)

    return render_template("form.html", max_upload_mb=25)

if __name__ == "__main__":
    app.run(debug=True)
