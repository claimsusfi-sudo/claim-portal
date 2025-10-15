from flask import Flask, render_template, request, redirect, flash, url_for, send_from_directory
import os
import uuid
import base64
import sendgrid
from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition

app = Flask(__name__)
app.secret_key = "secret-key"
app.config["UPLOAD_FOLDER"] = "uploads"
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # 25 MB per request

# Ensure upload folder exists
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# =======================
# EMAIL SETTINGS (SendGrid)
# =======================
SENDGRID_API_KEY = "b513b321fa8995f3140314b153291c5a"  # For testing only
EMAIL_SENDER = "arthur.cuigniez@usfloors.be"  # Must be verified in SendGrid
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
        for f in issue_files + evidence_files:
            f.seek(0)

        # -----------------------
        # Save files locally
        # -----------------------
        issue_paths = []
        evidence_paths = []

        def save_files(file_list, target_list):
            for file in file_list:
                if file.filename != "":
                    filename = f"{uuid.uuid4().hex}_{file.filename}"
                    file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                    file.save(file_path)
                    target_list.append(file_path)

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
        # Send email with SendGrid
        # -----------------------
        try:
            message = Mail(
                from_email=EMAIL_SENDER,
                to_emails=RECIPIENTS,
                subject='New Coretec Claim Submission',
                plain_text_content=body
            )

            # Attach files if total size <= 25 MB
            if total_size <= app.config["MAX_CONTENT_LENGTH"]:
                for file_path in issue_paths + evidence_paths:
                    with open(file_path, "rb") as f:
                        encoded = base64.b64encode(f.read()).decode()
                    attachment = Attachment(
                        FileContent(encoded),
                        FileName(os.path.basename(file_path)),
                        FileType("application/octet-stream"),
                        Disposition("attachment")
                    )
                    message.add_attachment(attachment)

            sg = sendgrid.SendGridAPIClient(api_key=SENDGRID_API_KEY)
            response = sg.send(message)

            if response.status_code in [200, 202]:
                flash("Claim submitted successfully! Email sent via SendGrid.", "success")
            else:
                flash(f"Claim saved, but SendGrid email failed: {response.status_code}", "error")

        except Exception as e:
            flash(f"Claim saved, but SendGrid email failed: {e}", "error")

        return redirect(request.url)

    return render_template("form.html", max_upload_mb=25)

if __name__ == "__main__":
    app.run(debug=True)
