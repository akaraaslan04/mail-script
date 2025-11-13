Personalized Email Sender Script

A robust Python utility for secure, dynamic email campaigns using CSV data and separate templates.

Features

Personalization: Uses CSV data to dynamically fill placeholders in subject and body templates.

HTML Support: Sends emails using the multipart/alternative structure for professional HTML bodies.

Safe Formatting: Employs a unique function to prevent errors from non-placeholder braces (e.g., in CSS or JSON code blocks).

Dry-Run Mode: Test content generation and formatting safely without ever connecting to the SMTP server.

Logging: Automatically creates success and failure CSV log files with full details.

SMTP Security: Enforces security by using SMTP_SSL (Port 465) for connecting to the server (defaulting to Gmail).

Setup and Usage

Prerequisites

You need Python 3.x installed. The script uses only standard libraries, so no external installations are required.

Configuration File (config.json)

Create this file in the script's directory to hold your sender credentials.
Note on Gmail: You must use an App Password instead of your regular account password if you have 2FA enabled.

{
"sender_email": "your_email@gmail.com",
"sender_password": "your_gmail_app_password",
"sender_name": "Your Company Name"
}

Data File (recipients.csv)

Your recipient data must be in a CSV file. The column headers become the personalization variables you can use in your templates.

E-Posta Adresi,Ad-Soyad,Unvan,Takim
alice@example.com,Alice Smith,Developer,Engineering
bob@example.com,Bob Johnson,Designer,Creative

Template Files (subject.txt and body.html)

Create separate text files for the subject and body. Use the CSV column headers (or built-in variables like {SENDER_NAME}) as placeholders, enclosed in curly braces {}.

A. Subject Template (subject.txt)

Your Project Update: {Takim} - {Unvan}

B. Body Template (body.html)

The body can be plain text or HTML. Note the use of doubled braces ({{ and }}) for CSS to avoid conflicts with the safe formatting logic.

<!DOCTYPE html><html><head>

<style>
    /* CSS is fine here */
    body {{ font-family: sans-serif; }}
    .highlight {{ color: #007bff; font-weight: bold; }}
</style></head><body>
<p>Dear {Ad-Soyad},</p>
<p>This is your personalized update for the **{Takim}** team.</p>
<p>We are excited about the work our <span class="highlight">{Unvan}</span>s are doing!</p>
<p>The built-in variable **{SENDER_NAME}** is available as well.</p>
<br>
<p>Sincerely,</p>
<p>{SENDER_NAME}</p></body></html>


Execution

Run the script from your terminal using the following command structure:

python your_script_name.py <data_file.csv> <subject_file.txt> <body_file.html> [options]

Example (Real Send)

python email_sender.py recipients.csv subject.txt body.html

Example (Dry-Run)

The --dry-run flag will format the emails and print them to the console without connecting to the SMTP server.

python email_sender.py recipients.csv subject.txt body.html --dry-run

Example (Custom Column Names)

If your CSV columns are named differently (e.g., English headers), use the optional arguments:

python email_sender.py data.csv subj.txt body.html --email-col 'Email' --name-col 'Full Name'

Command Line Arguments

Argument | Description | Default | Mandatory
data_source_file | The path to your recipient CSV file. | N/A | Yes
subject_template_file | The path to your subject TXT file. | N/A | Yes
body_template_file | The path to your body HTML/TXT file. | N/A | Yes
--dry-run | Flag to format and print, but not send, emails. | False | No
--email-col | The CSV column header for the recipient's email address. | E-Posta Adresi | No
--name-col | The CSV column header for the recipient's name. | Ad-Soyad | No

Logging

The script automatically creates and appends to two log files in the script's directory:

sent_emails.csv: Logs details of successfully sent emails, grouped by identical subject/body preview to keep the log file concise.

failed_emails.csv: Logs details and the reason for any failed or skipped email attempts (e.g., missing personalization data, SMTP error).
