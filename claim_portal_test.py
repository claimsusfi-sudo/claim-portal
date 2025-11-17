from flask import Flask, render_template, request, redirect, flash, send_from_directory
import os
import uuid
import smtplib
import base64
from email.message import EmailMessage

app = Flask(__name__)
app.secret_key = "srys sizr telm tvbq"
app.config["UPLOAD_FOLDER"] = "uploads"
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # 25 MB

# Ensure upload folder exists
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# ------------------------------
# Gmail SMTP settings
# ------------------------------
EMAIL_SENDER = "claims.usfi@gmail.com"
EMAIL_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")  # store app password in env variable
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
        link_public = request.form.get("link_public")

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
        for f in issue_files + evidence_files:
            f.seek(0)

        issue_paths = []
        evidence_paths = []

        def save_files(file_list, target_list):
            for file in file_list:
                if file.filename != "":
                    filename = f"{uuid.uuid4().hex}_{file.filename}"
                    path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                    file.save(path)
                    target_list.append(path)

        save_files(issue_files, issue_paths)
        save_files(evidence_files, evidence_paths)

        # -----------------------
        # Build email body
        # -----------------------
        body = "Coretec Claim Submission Details:\n\n"
        for key, value in request.form.items():
            body += f"{key}: {value}\n"
        body += f"Defects selected: {', '.join(defects_selected)}\n\n"

        if total_size > app.config["MAX_CONTENT_LENGTH"]:
            body += f"External link provided: {external_link} (Link is public: {link_public})\n"
        else:
            if issue_paths:
                body += "Issue Photos attached:\n"
                for f in issue_paths:
                    body += f" - {os.path.basename(f)}\n"
            if evidence_paths:
                body += "Evidence Photos attached:\n"
                for f in evidence_paths:
                    body += f" - {os.path.basename(f)}\n"

        # -----------------------
        # Send email via Gmail SMTP
        # -----------------------
        try:
            msg = EmailMessage()
            msg["Subject"] = "New Coretec Claim Submission"
            msg["From"] = EMAIL_SENDER
            msg["To"] = ", ".join(RECIPIENTS)
            msg.set_content(body)

            # Attach files if not too big
            for fpath in issue_paths + evidence_paths:
                filesize = os.path.getsize(fpath)
                if filesize <= 25 * 1024 * 1024:  # 25 MB limit
                    with open(fpath, "rb") as f:
                        file_data = f.read()
                    msg.add_attachment(file_data,
                                       maintype="application",
                                       subtype="octet-stream",
                                       filename=os.path.basename(fpath))
                else:
                    body += f"\n{os.path.basename(fpath)} is too large to attach."

            # Send email
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
                smtp.login(EMAIL_SENDER, EMAIL_PASSWORD)
                smtp.send_message(msg)

            flash("Claim submitted successfully! Email sent via Gmail.", "success")

        except Exception as e:
            flash(f"Claim saved, but Gmail email failed: {e}", "error")

        return redirect(request.url)

    return render_template("form.html", max_upload_mb=25)


if __name__ == "__main__":
    app.run(debug=True)
