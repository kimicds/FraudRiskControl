**FraudRiskControl** is an AI-powered web application for detecting fraudulent transactions. It allows users to enter transaction details, checks for potential fraud using a machine learning model, captures sender location, updates balances, and alerts investigators via email if suspicious activity is detected.

---

## Features

- **Transaction Assessment**: Evaluate transactions in real-time.
- **Fraud Detection**: AI model predicts if a transaction is fraudulent.
- **Email Alerts**: Sends notification to investigator if fraud is detected.
- **Location Capture**: Captures sender's location automatically; defaults to "Unknown" if denied.
- **Balance Validation**: Checks sender's balance against transaction amount.
- **Responsive UI**: Clean and intuitive interface built with Bootstrap.

---

## Tech Stack

- **Backend**: Python, Flask  
- **Machine Learning**: Scikit-learn / Joblib model  
- **Frontend**: HTML, CSS, Bootstrap  
- **Email Notifications**: SMTP with Gmail  
- **Environment Variables**: `.env` for email credentials and model path  

---

## Installation

1. Clone the repository:

```bash
git clone https://github.com/kimicds/FraudRiskControl.git
cd FraudRiskControl
