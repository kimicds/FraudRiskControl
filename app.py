import os
import joblib
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, session, flash
from dotenv import load_dotenv
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import re
import datetime

load_dotenv()

EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
MODEL_PATH = os.getenv("MODEL_PATH", "fraud_detection_model.pkl")

app = Flask(__name__)
app.secret_key = "fraud_secret_key"  # Minimal secret for session handling

# Load ML model
model = joblib.load(MODEL_PATH)

def is_valid_email(email):
    regex = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(regex, email) is not None

def send_fraud_alert(record, receiver_email):
    try:
        subject = "🚨 Fraud Transaction Alert"
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        location = record.get("sender_location", "Unknown")

        body = f"""
        <html>
        <body>
            <h2 style='color:red;'>Fraud Alert Notification</h2>
            <p><strong>Date/Time:</strong> {now}</p>
            <p><strong>Sender Account:</strong> {record['sender_account']}</p>
            <p><strong>Receiver Account:</strong> {record['receiver_account']}</p>
            <p><strong>Amount:</strong> ₦{record['transaction_amount']}</p>
            <p><strong>Transaction Type:</strong> {record['transaction_type']}</p>
            <p><strong>Sender Location:</strong> {location}</p>
            <hr>
            <p>Please investigate immediately.</p>
        </body>
        </html>
        """

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = EMAIL_USER
        msg["To"] = receiver_email
        msg.attach(MIMEText(body, "html"))

        # Safe email sending with exception handling
        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as server:
                server.login(EMAIL_USER, EMAIL_PASS)
                server.sendmail(EMAIL_USER, receiver_email, msg.as_string())
            return True
        except smtplib.SMTPException as e:
            print("SMTP error:", e)
            return False
        except Exception as e:
            print("Email send failed:", e)
            return False

    except Exception as e:
        print("Unexpected error in send_fraud_alert:", e)
        return False

# Root points to About page
@app.route("/")
@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/data-entry", methods=["GET", "POST"])
def data_entry():
    if request.method == "POST":
        sender_location = request.form.get("sender_location", "Unknown") or "Unknown"

        data = {
            "transaction_hour": int(request.form["transaction_hour"]),
            "transaction_amount": float(request.form["transaction_amount"]),
            "sender_balance_before": float(request.form["sender_balance_before"]),
            "receiver_balance_before": float(request.form["receiver_balance_before"]),
            "transaction_type": request.form["transaction_type"],
            "sender_account": request.form["sender_account"],
            "receiver_account": request.form["receiver_account"],
            "investigator_email": request.form["investigator_email"],
            "sender_location": sender_location
        }

        # Validate balance
        if data["transaction_amount"] > data["sender_balance_before"]:
            flash("Error: Sender balance is insufficient for this transaction.", "danger")
            return redirect(url_for("data_entry"))

        # Validate investigator email
        if not is_valid_email(data["investigator_email"]):
            flash("Error: Investigator email is invalid.", "danger")
            return redirect(url_for("data_entry"))

        session["transaction_data"] = data
        return redirect(url_for("predict"))

    return render_template("data_entry.html")

@app.route("/predict")
def predict():
    data = session.get("transaction_data")
    if not data:
        flash("No transaction data found. Please enter transaction details first.", "warning")
        return redirect(url_for("data_entry"))

    origin_balance_after = data["sender_balance_before"] - data["transaction_amount"]
    destination_balance_after = data["receiver_balance_before"] + data["transaction_amount"]

    tx = {t: 0 for t in ["CASH_IN", "CASH_OUT", "DEBIT", "PAYMENT", "TRANSFER"]}
    tx[data["transaction_type"]] = 1

    X = pd.DataFrame([[data["transaction_hour"],
                       data["transaction_amount"],
                       data["sender_balance_before"],
                       origin_balance_after,
                       data["receiver_balance_before"],
                       destination_balance_after,
                       tx["CASH_IN"], tx["CASH_OUT"], tx["DEBIT"], tx["PAYMENT"], tx["TRANSFER"]]],
                     columns=["transaction_hour","transaction_amount",
                              "origin_balance_before","origin_balance_after",
                              "destination_balance_before","destination_balance_after",
                              "transaction_type_CASH_IN","transaction_type_CASH_OUT",
                              "transaction_type_DEBIT","transaction_type_PAYMENT",
                              "transaction_type_TRANSFER"])

    prediction = int(model.predict(X)[0])
    result = "Fraud" if prediction == 1 else "Not Fraud"

    email_status_message = None
    if result == "Fraud":
        if is_valid_email(data["investigator_email"]):
            email_sent = send_fraud_alert(data, data["investigator_email"])
            if email_sent:
                email_status_message = "Fraud detected. Email alert sent to investigator."
            else:
                email_status_message = "Fraud detected but the investigator email could not be delivered."
        else:
            email_status_message = "Fraud detected but investigator email is invalid!"

    data["origin_balance_after"] = origin_balance_after
    data["destination_balance_after"] = destination_balance_after

    session.pop("transaction_data", None)
    return render_template("predict.html", result=result, alert_message=email_status_message, data=data)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
