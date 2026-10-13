# NutriScan

NutriScan is an AI-powered food ingredient analysis project for recognizing ingredients and identifying potential health concerns. The Streamlit application entry point is `app.py`.

Local environment files, databases, uploads, reports, and stored user/scan data are excluded from this repository.

## Run locally

Install the dependencies and start the app:

```sh
pip install -r requirements.txt
streamlit run app.py
```

## Deploy publicly

This repository is prepared for Streamlit Community Cloud. Sign in at
[share.streamlit.io](https://share.streamlit.io/), create an app from this
repository's `main` branch, and set the app file to `app.py`. The dependency
list is in `requirements.txt`.

The hosted app needs Supabase secrets configured in Streamlit's app settings
for accounts and scan history to persist across restarts. Configure
`SUPABASE_URL` and `SUPABASE_KEY` there if using Supabase. Never commit these
values or a local `.env` file.

Select Python 3.12 for the deployment; the OCR runtime dependency does not yet
support Python 3.13.

The `packages.txt` file lists the Linux system libraries OpenCV needs for OCR
on Streamlit Community Cloud.

To enable password-reset emails, add `GMAIL_USER` and `GMAIL_APP_PASSWORD` as
root-level entries in the app's Streamlit secrets. Generate a Gmail app
password from a Google account with 2-Step Verification enabled. Reset codes
are not displayed when email delivery is unconfigured.
