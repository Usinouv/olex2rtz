import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging

def send_contact_email(name, email, subject, message, log_file_path="app.log"):
    sender_email = os.getenv("SENDER_EMAIL")
    receiver_email = os.getenv("RECEIVER_EMAIL")
    password = os.getenv("EMAIL_PASSWORD")

    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = os.getenv("SMTP_PORT")
    if not smtp_port or not smtp_port.isdigit():
        logging.error("SMTP_PORT is not defined or invalid.")
        return False, "SMTP configuration is invalid."

    smtp_port = int(smtp_port)

    recent_logs = []
    if os.path.exists(log_file_path):
        with open(log_file_path, "r") as log_file:
            recent_logs = log_file.readlines()[-25:]

    logs_text = "\n".join(line.strip() for line in recent_logs)

    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = receiver_email
    msg["Subject"] = f"[Olex2RTZ] {subject}"

    body = f"""
    Nom : {name}
    E-mail : {email}
    Sujet : {subject}
    Message :
    {message}

    --- Logs récents ---
    {logs_text}
    """
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, password)
            server.sendmail(sender_email, receiver_email, msg.as_string())
        return True, "Message envoyé avec succès."
    except Exception as e:
        logging.error(f"Erreur lors de l'envoi d'e-mail : {e}")
        return False, "Erreur lors de l'envoi du message."
