import csv
import smtplib
import ssl
import sys
import os
import datetime
import argparse
import json 
from email.message import EmailMessage

# --- NEW CONFIGURATION (Constants) ---

# These constants are for the underlying infrastructure and should not change frequently.
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465
CONFIG_FILE_NAME = "config.json"
LOG_SENT_FILE = "sent_emails.csv"
LOG_FAILED_FILE = "failed_emails.csv"

# In-memory group accumulators (subject + preview -> recipients)
sent_groups = {}
failed_groups = {}
# --- END OF CONFIGURATION ---

def load_config():
    """
    Reads sender email, app password, and sender name from config.json.
    """
    try:
        with open(CONFIG_FILE_NAME, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # Check for essential keys
        if not all(key in config for key in ['sender_email', 'sender_password', 'sender_name']):
            print(f"Error: '{CONFIG_FILE_NAME}' is missing required information. 'sender_email', 'sender_password', and 'sender_name' are mandatory.")
            return None
        
        return config
    except FileNotFoundError:
        print(f"--- ERROR: '{CONFIG_FILE_NAME}' file not found. ---")
        print("Please create a config.json file with email credentials and sender name.")
        return None
    except json.JSONDecodeError:
        print(f"Error: '{CONFIG_FILE_NAME}' is not a valid JSON format.")
        return None
    except Exception as e:
        print(f"An unexpected error occurred while reading the config file: {e}")
        return None


def load_text_file(filepath):
    """
    Reads the full content of a given text file (for subject or template).
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content:
                print(f"Error: '{filepath}' file is empty.")
                return None
            return content
    except FileNotFoundError:
        print(f"--- ERROR: '{filepath}' file not found. ---")
        return None
    except Exception as e:
        print(f"An error occurred while reading '{filepath}': {e}")
        return None


def safe_format(template, mapping):
    """
    Escapes all braces, then restores known placeholders before formatting.
    This prevents interpreting non-placeholder braces (like CSS) as format fields.
    """
    # Escape all braces so they become literals
    s = template.replace('{', '{{').replace('}', '}}')
    # Restore the placeholders we actually want to format
    for k in mapping.keys():
        s = s.replace('{{' + k + '}}', '{' + k + '}')
    
    return s.format(**mapping)


def ensure_log_file(path, headers):
    """Ensures a CSV log file exists with the provided headers."""
    if not os.path.exists(path):
        try:
            with open(path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
        except Exception as e:
            print(f"Warning: could not create log file '{path}': {e}")


def log_sent(recipient_email, recipient_name, subject, body):
    """Accumulates sent entries to in-memory group."""
    key = (subject or '', (body or '')[:400])
    sent_groups.setdefault(key, {'emails': [], 'names': []})
    sent_groups[key]['emails'].append(recipient_email or '')
    sent_groups[key]['names'].append(recipient_name or '')


def log_failed(recipient_email, recipient_name, subject, body, reason):
    """Accumulates failed entries to in-memory group."""
    key = (subject or '', (body or '')[:400])
    failed_groups.setdefault(key, {'emails': [], 'names': [], 'reasons': []})
    failed_groups[key]['emails'].append(recipient_email or '')
    failed_groups[key]['names'].append(recipient_name or '')
    failed_groups[key]['reasons'].append(reason or '')


def flush_logs():
    """Writes grouped sent/failed entries from memory to CSV log files."""
    # Write sent groups
    try:
        if sent_groups:
            # Use 'a' (append) mode since headers were created by ensure_log_file
            with open(LOG_SENT_FILE, 'a', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                for (subject, preview), data in sent_groups.items():
                    ts = datetime.datetime.utcnow().isoformat()
                    emails = ';'.join(data['emails'])
                    names = ';'.join(data['names'])
                    writer.writerow([ts, emails, names, subject, preview]) 
    except Exception as e:
        print(f"Warning: failed to flush '{LOG_SENT_FILE}': {e}")

    # Write failed groups
    try:
        if failed_groups:
            with open(LOG_FAILED_FILE, 'a', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                for (subject, preview), data in failed_groups.items():
                    ts = datetime.datetime.utcnow().isoformat()
                    emails = ';'.join(data['emails'])
                    names = ';'.join(data['names'])
                    reasons = ';'.join(data['reasons'])
                    writer.writerow([ts, emails, names, subject, preview, reasons])
    except Exception as e:
        print(f"Warning: failed to flush '{LOG_FAILED_FILE}': {e}")


def send_single_email(server, sender_email, sender_name, recipient_data, subject_template, body_template, email_column, name_column):
    """
    Uses an existing server connection to send a single personalized email.
    Takes column names as parameters for generalized use.
    """
    
    # Extract recipient columns
    recipient_name = recipient_data.get(name_column, 'Unknown')
    recipient_email = recipient_data.get(email_column)

    # --- Create the Email Subject and Body from Templates ---
    try:
        # Prepare mapping (include all data from the row)
        mapping = recipient_data.copy()
        mapping['sender_name'] = sender_name
        mapping['SENDER_NAME'] = sender_name 
        
        # Convert None values to empty strings to prevent formatting errors
        for key, value in mapping.items():
            if value is None:
                mapping[key] = ''
            # Also handle non-string types if they might be in the CSV
            elif not isinstance(value, str):
                 mapping[key] = str(value)

        # Format the subject and body safely
        subject = safe_format(subject_template, mapping)
        body = safe_format(body_template, mapping)

        # If we couldn't find a recipient email, skip and warn
        if not recipient_email:
            print(f"Skipping: No valid recipient email found for {recipient_name}. Row: {recipient_data}")
            log_failed(None, recipient_name, subject, body, 'no recipient email')
            return False
        
        # Create the EmailMessage object
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = f"{sender_name} <{sender_email}>"
        msg['To'] = recipient_email
        msg.add_alternative(body, subtype='html')

        # --- Send the Email ---
        server.send_message(msg)
        print(f"Successfully sent email to: {recipient_name} ({recipient_email})")
        log_sent(recipient_email, recipient_name, subject, body)
        return True
        
    except KeyError as e:
        # Template variable missing in CSV columns or mapping
        print(f"Error: Could not format email for {recipient_name}. Template error: Variable {e} not found in CSV columns or mapping.")
        subj = locals().get('subject', '')
        bod = locals().get('body', '')
        log_failed(recipient_email, recipient_name, subj, bod, f"template KeyError: {e}")
        return False
    except smtplib.SMTPException as e:
        print(f"Error: Unable to send email to {recipient_name}. Reason: {e}")
        subj = locals().get('subject', '')
        bod = locals().get('body', '')
        log_failed(recipient_email, recipient_name, subj, bod, f"SMTPException: {e}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred for {recipient_name}: {e}")
        subj = locals().get('subject', '')
        bod = locals().get('body', '')
        log_failed(recipient_email, recipient_name, subj, bod, f"Exception: {e}")
        return False


def main():
    """
    Main function: Loads configuration, parses command-line arguments, and runs the email loop.
    """
    
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Sends personalized emails using CSV data.')
    parser.add_argument('data_source_file', help='The name of the CSV file containing recipient data.')
    parser.add_argument('subject_template_file', help='The name of the TXT file containing the email subject template.')
    parser.add_argument('body_template_file', help='The name of the file containing the email body template (HTML/TXT).')
    parser.add_argument('--dry-run', action='store_true', help='Format and print messages without sending.')
    parser.add_argument('--email-col', default='E-Posta Adresi', help='The CSV column name for the recipient email address.')
    parser.add_argument('--name-col', default='Ad-Soyad', help='The CSV column name for the recipient name.')
    
    args = parser.parse_args()
    
    dry_run = args.dry_run
    data_source_file = args.data_source_file
    subject_template_file = args.subject_template_file
    body_template_file = args.body_template_file
    email_column = args.email_col
    name_column = args.name_col

    # Load Configuration
    config = load_config()
    if not config and not dry_run:
        sys.exit(1)
    
    # Check credentials for actual sending
    if not dry_run and not all(config.get(k) for k in ['sender_email', 'sender_password']):
        print("Program stopped. Please check for missing credentials in 'config.json'.")
        sys.exit(1)

    # Load Templates
    subject_template = load_text_file(subject_template_file)
    body_template = load_text_file(body_template_file)

    if not all([subject_template, body_template]):
        print("Program stopped. Please check for missing template files.")
        sys.exit(1) 

    # Determine sender details (use placeholders for dry-run if config failed)
    sender_email = config.get('sender_email', 'no-reply@example.com') if config else 'no-reply@example.com'
    sender_password = config.get('sender_password', '') if config else ''
    sender_name = config.get('sender_name', 'Unknown Sender') if config else 'Unknown Sender'

    print(f"\nProcess Starting... (Dry-run: {dry_run})")
    print(f"Data Source: {data_source_file}")
    print(f"Sender: {sender_name} <{sender_email}>")

    # Ensure log files exist with headers
    ensure_log_file(LOG_SENT_FILE, ['timestamp', 'recipient_emails', 'recipient_names', 'subject', 'body_preview'])
    ensure_log_file(LOG_FAILED_FILE, ['timestamp', 'recipient_emails', 'recipient_names', 'subject', 'body_preview', 'reason'])

    # Open the CSV file and process recipients
    try:
        with open(data_source_file, mode='r', encoding='utf-8') as file:
            try:
                # Assuming DictReader is used, it expects a header row
                csv_reader = csv.DictReader(file)
                # Quick check for the critical email column
                if email_column not in csv_reader.fieldnames:
                    print(f"Critical Error: Email column '{email_column}' not found in the CSV file headers: {csv_reader.fieldnames}")
                    sys.exit(1)
            except Exception as e:
                print(f"CSV reading error occurred: {e}")
                sys.exit(1)

            total = 0
            sent = 0
            skipped = 0

            # --- Dry-run or Real Send ---
            if dry_run:
                # Dry-run: Format and print messages
                for row in csv_reader:
                    total += 1
                    try:
                        # Prepare mapping and format similarly to send_single_email
                        mapping = row.copy()
                        mapping['sender_name'] = sender_name
                        mapping['SENDER_NAME'] = sender_name
                        for key, value in mapping.items():
                            if value is None:
                                mapping[key] = ''
                                
                        subject = safe_format(subject_template, mapping)
                        body = safe_format(body_template, mapping)
                        
                        recipient_name = row.get(name_column, 'Unknown')
                        recipient_email = row.get(email_column)
                        
                        if not recipient_email:
                            print(f"DRY-RUN: Skipping row #{total} - no recipient email: {recipient_name}")
                            log_failed(recipient_email, recipient_name, subject, body, 'no recipient email')
                            skipped += 1
                            continue
                            
                        print(f"\n--- DRY-RUN Message #{total} ---")
                        print(f"To: {recipient_email} ({recipient_name})")
                        print(f"Subject: {subject}")
                        print("Body preview:")
                        print(body[:500] + "..." if len(body) > 500 else body)
                        log_sent(recipient_email, recipient_name, subject, body)
                        sent += 1
                    except Exception as e:
                        print(f"DRY-RUN Error formatting row #{total}: {e}")
                        skipped += 1
                
                print(f"\nDRY-RUN CSV rows processed: {total}, messages formatted: {sent}, skipped: {skipped}")
            
            else:
                # Real Send: Connect to SMTP and send messages
                context = ssl.create_default_context()
                try:
                    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context) as server:
                        server.login(sender_email, sender_password)
                        print("Login successful. Starting to send emails...")

                        for row in csv_reader:
                            total += 1
                            ok = send_single_email(
                                server,
                                sender_email,
                                sender_name,
                                row,
                                subject_template,
                                body_template,
                                email_column,
                                name_column
                            )
                            if ok:
                                sent += 1
                            else:
                                skipped += 1
                        
                        print(f"\nCSV rows processed: {total}, sent: {sent}, skipped: {skipped}")
                
                except smtplib.SMTPAuthenticationError:
                    print("\n--- CRITICAL ERROR ---")
                    print("Login failed. Program stopped.")
                    print(f"Please check your email and application password in '{CONFIG_FILE_NAME}'.")
                except Exception as e:
                    print(f"An unexpected error occurred during the SMTP connection: {e}")


    except FileNotFoundError:
        print(f"Error: The file '{data_source_file}' was not found.")
        print("Please ensure the CSV file is in the same directory as the script.")
    except Exception as e:
        print(f"An unexpected critical error occurred: {e}")

    print("\nEmail process finished.")

    # Flush grouped logs to files
    flush_logs()


# Run the main function when the script is executed
if __name__ == "__main__":
    main()
