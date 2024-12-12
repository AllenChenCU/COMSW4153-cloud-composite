import os
import smtplib
import requests
import ssl
from flask import jsonify
import functions_framework


def send_email(to_email, subject, message):
    smtp_server = "smtp.gmail.com"
    smtp_port = 465
    sender_email = os.getenv("sender_email")
    sender_password = os.getenv("sender_password")

    context = ssl.create_default_context()
    text = f"""
    Subject: {subject}

    {message}
    """

    # Send the email
    with smtplib.SMTP_SSL(smtp_server, smtp_port, context=context) as server:
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, to_email, text)


@functions_framework.http
def email_notification(request):
    """
    HTTP-triggered Cloud Function
    Expects a POST request with JSON body containing 'to_email', 'subject', and 'message'
    """
    try:
        request_json = request.get_json()
        to_email = request_json.get("to_email")
        subject = request_json.get("subject")
        message = request_json.get("message")

        if not all([to_email, subject, message]):
            return jsonify({"error": "Missing required fields"}), 400

        send_email(to_email, subject, message)
        return jsonify({"status": "Email sent successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

