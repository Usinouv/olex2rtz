import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app

def send_contact_email(name, email, subject, message):
    sender_email = os.getenv("SENDER_EMAIL")
    receiver_email = os.getenv("RECEIVER_EMAIL")
    password = os.getenv("EMAIL_PASSWORD")

    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = os.getenv("SMTP_PORT")
    if not smtp_port or not smtp_port.isdigit():
        current_app.logger.error("SMTP_PORT is not defined or invalid.")
        return False, "SMTP configuration is invalid."

    smtp_port = int(smtp_port)

    logs_text = "No log file found or configured."
    log_handler = next((h for h in current_app.logger.handlers if isinstance(h, logging.FileHandler)), None)
    if log_handler:
        log_file_path = log_handler.baseFilename
        if os.path.exists(log_file_path):
            with open(log_file_path, "r") as log_file:
                recent_logs = log_file.readlines()[-25:]
            logs_text = "\n".join(line.strip() for line in recent_logs)

    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = receiver_email
    msg["Subject"] = f"[Olex2RTZ Contact] {subject}"

    body = f"""
    Name: {name}
    Email: {email}
    Subject: {subject}
    Message:
    {message}

    --- Recent Logs ---
    {logs_text}
    """
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, password)
            server.sendmail(sender_email, receiver_email, msg.as_string())
        current_app.logger.info(f"Contact email sent successfully from {email} with subject: {subject}")
        return True, "Message sent successfully."
    except Exception as e:
        current_app.logger.error(f"Email sending failed: {e}", exc_info=True)
        return False, "Error sending message."
