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
app.secret_key = os.getenv("SECRET_KEY")

if not app.secret_key:
    raise ValueError("SECRET_KEY not set in environment variables")

# -------------------------------
# SAFE MODEL LOADING
# -------------------------------
if not os.path.exists(MODEL_PATH):
    raise FileNotFoundError(f"Model not found at {MODEL_PATH}")

model = joblib.load(MODEL_PATH)

# -------------------------------
# UTILITIES
# -------------------------------
def is_valid_email(email):
    regex = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(regex, email) is not None


def send_fraud_alert(record, receiver_email):
    if not EMAIL_USER or not EMAIL_PASS:
        print("Email credentials not set")
        return False

    try:
        subject = "Fraud Transaction Alert"
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

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASS)
            server.sendmail(EMAIL_USER, receiver_email, msg.as_string())

        return True

    except Exception as e:
        print("Email send failed:", e)
        return False


# -------------------------------
# ROUTES
# -------------------------------
@app.route("/")
def home():
    return redirect(url_for("about"))


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/data-entry", methods=["GET", "POST"])
def data_entry():
    if request.method == "POST":
        try:
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

        except (ValueError, KeyError):
            flash("Invalid input. Please check your entries.", "danger")
            return redirect(url_for("data_entry"))

        # -------------------------------
        # VALIDATIONS
        # -------------------------------
        if data["transaction_amount"] <= 0:
            flash("Amount must be positive.", "danger")
            return redirect(url_for("data_entry"))

        if not (0 <= data["transaction_hour"] <= 23):
            flash("Transaction hour must be between 0 and 23.", "danger")
            return redirect(url_for("data_entry"))

        if data["transaction_amount"] > data["sender_balance_before"]:
            flash("Sender balance is insufficient.", "danger")
            return redirect(url_for("data_entry"))

        if not is_valid_email(data["investigator_email"]):
            flash("Invalid investigator email.", "danger")
            return redirect(url_for("data_entry"))

        session["transaction_data"] = data
        return redirect(url_for("predict"))

    return render_template("data_entry.html")


@app.route("/predict")
def predict():
    data = session.get("transaction_data")

    if not data:
        flash("No transaction data found.", "warning")
        return redirect(url_for("data_entry"))

    try:
        origin_balance_after = data["sender_balance_before"] - data["transaction_amount"]
        destination_balance_after = data["receiver_balance_before"] + data["transaction_amount"]

        tx_types = ["CASH_IN", "CASH_OUT", "DEBIT", "PAYMENT", "TRANSFER"]
        tx = {t: 0 for t in tx_types}

        if data["transaction_type"] not in tx:
            flash("Invalid transaction type.", "danger")
            return redirect(url_for("data_entry"))

        tx[data["transaction_type"]] = 1

        X = pd.DataFrame([[
            data["transaction_hour"],
            data["transaction_amount"],
            data["sender_balance_before"],
            origin_balance_after,
            data["receiver_balance_before"],
            destination_balance_after,
            tx["CASH_IN"], tx["CASH_OUT"], tx["DEBIT"], tx["PAYMENT"], tx["TRANSFER"]
        ]], columns=[
            "transaction_hour", "transaction_amount",
            "origin_balance_before", "origin_balance_after",
            "destination_balance_before", "destination_balance_after",
            "transaction_type_CASH_IN", "transaction_type_CASH_OUT",
            "transaction_type_DEBIT", "transaction_type_PAYMENT",
            "transaction_type_TRANSFER"
        ])

        prediction = int(model.predict(X)[0])
        result = "Fraud" if prediction == 1 else "Not Fraud"

    except Exception as e:
        flash(f"Prediction failed: {str(e)}", "danger")
        return redirect(url_for("data_entry"))

    # -------------------------------
    # EMAIL ALERT
    # -------------------------------
    email_status_message = None

    if result == "Fraud":
        email_sent = send_fraud_alert(data, data["investigator_email"])

        if email_sent:
            email_status_message = "Fraud detected. Email sent to investigator."
        else:
            email_status_message = "Fraud detected but email failed."

    # -------------------------------
    # STORE RESULTS
    # -------------------------------
    data["origin_balance_after"] = origin_balance_after
    data["destination_balance_after"] = destination_balance_after

    session.pop("transaction_data", None)

    return render_template(
        "predict.html",
        result=result,
        alert_message=email_status_message,
        data=data
    )


# -------------------------------
# RUN (RENDER SAFE)
# -------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)