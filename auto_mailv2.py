import csv
import smtplib
import ssl
import sys
import re
import os
import datetime
import argparse
from email.message import EmailMessage

# --- CONFIGURATION ---
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465
#CSV_MAIN_FILE_NAME = "mentorluk kabul son.csv"
CSV_TEST_FILE_NAME = "test.csv" 
CSV_FILE_NAME = CSV_TEST_FILE_NAME  # Currently using the test file
CONFIG_FILE_NAME = "config.txt"
SUBJECT_FILE_NAME = "subject.txt"        
TEMPLATE_FILE_NAME = "email_template.html" 
SENDER_NAME = "MBK Organizasyon Komitesi Yönetim Kurulu"
LOG_SENT_FILE = "sent_emails.csv"
LOG_FAILED_FILE = "failed_emails.csv"
# --- END OF CONFIGURATION ---


def load_credentials():
    """
    Reads sender email and app password from config.txt.
    """
    try:
        with open(CONFIG_FILE_NAME, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            if len(lines) < 2:
                print(f"Hata: '{CONFIG_FILE_NAME}' dosyası eksik bilgi içeriyor.")
                return None, None
            sender_email = lines[0].strip()
            sender_password = lines[1].strip()
            if not sender_email or not sender_password:
                print(f"Hata: '{CONFIG_FILE_NAME}' dosyasındaki bilgiler okunamadı.")
                return None, None
            return sender_email, sender_password
    except FileNotFoundError:
        print(f"--- HATA: '{CONFIG_FILE_NAME}' dosyası bulunamadı. ---")
        return None, None
    except Exception as e:
        print(f"Config dosyası okunurken beklenmedik bir hata oluştu: {e}")
        return None, None


def load_text_file(filename):
    """
    Reads the full content of a given text file (for subject or template).
    """
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            # Instead of using readline() for subject and read() for template,
            # it's safer to use read() for both and clean with strip().
            content = f.read().strip()
            if not content:
                print(f"Hata: '{filename}' dosyası boş.")
                return None
            return content
    except FileNotFoundError:
        print(f"--- HATA: '{filename}' dosyası bulunamadı. ---")
        return None
    except Exception as e:
        print(f"'{filename}' dosyası okunurken bir hata oluştu: {e}")
        return None


def safe_format(template, mapping):
    """Escape all braces, then restore known placeholders before formatting.
    This avoids interpreting CSS braces or other {...} as format fields.
    """
    # Escape all braces so they become literal
    s = template.replace('{', '{{').replace('}', '}}')
    # Restore the placeholders we actually want to format
    for k in mapping.keys():
        s = s.replace('{{' + k + '}}', '{' + k + '}')
    return s.format(**mapping)


def ensure_log_file(path, headers):
    """Ensure a CSV log file exists with the provided headers."""
    if not os.path.exists(path):
        try:
            with open(path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
        except Exception as e:
            print(f"Warning: could not create log file {path}: {e}")


def log_sent(recipient_email, recipient_name, subject, body):
    ts = datetime.datetime.utcnow().isoformat()
    try:
        with open(LOG_SENT_FILE, 'a', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([ts, recipient_email or '', recipient_name or '', subject or '', body or ''])
    except Exception as e:
        print(f"Warning: failed to write to {LOG_SENT_FILE}: {e}")


def log_failed(recipient_email, recipient_name, subject, body, reason):
    ts = datetime.datetime.utcnow().isoformat()
    try:
        with open(LOG_FAILED_FILE, 'a', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([ts, recipient_email or '', recipient_name or '', subject or '', body or '', reason])
    except Exception as e:
        print(f"Warning: failed to write to {LOG_FAILED_FILE}: {e}")


def send_personalized_email(server, sender_email, mentee_info, subject_template, body_template):
    """
    Uses an *existing* server connection to send a single personalized email.
    """
    # Extract data from the row
    mentee_name = mentee_info.get('Mentee Ad-Soyad')
    mentee_email = mentee_info.get('E-Posta Adresi')
    mentor_name = mentee_info.get('Mentör Ad-Soyad')

    # Clean up contact info
    mentor_linkedin = mentee_info.get('LinkedIn') if mentee_info.get('LinkedIn') not in (None, '-') else 'Belirtilmedi'
    mentor_email = mentee_info.get('E-Posta') if mentee_info.get('E-Posta') not in (None, '-') else 'Belirtilmedi'
    mentor_phone = mentee_info.get('Telefon Numarası') if mentee_info.get('Telefon Numarası') not in (None, '-') else 'Belirtilmedi'

    # use module-level safe_format

    try:
        # --- Create the Email Subject and Body from Templates ---

        # Prepare mapping (include both lowercase and uppercase sender key because templates vary)
        mapping = {
            'mentee_name': mentee_name,
            'mentor_name': mentor_name,
            'mentor_linkedin': mentor_linkedin,
            'mentor_email': mentor_email,
            'mentor_phone': mentor_phone,
            'sender_name': SENDER_NAME,
            'SENDER_NAME': SENDER_NAME,
        }

        # Format the subject and body safely
        subject = safe_format(subject_template, mapping)
        body = safe_format(body_template, mapping)

        # Create the EmailMessage object
        msg = EmailMessage()
        msg['Subject'] = subject
        # Use only the raw sender email in the From header to avoid email clients
        # showing a long display name above the subject. This keeps the subject
        # exactly as provided in `subject.txt`.
        msg['From'] = sender_email
        msg['To'] = mentee_email
        msg.add_alternative(body, subtype='html')

        # If we couldn't find a recipient email, skip and warn
        if not mentee_email:
            print(f"Skipping {mentee_name}: no valid recipient email found in row: {mentee_info}")
            return False

        # --- Send the Email ---
        server.send_message(msg)
        print(f"Successfully sent email to: {mentee_name} ({mentee_email})")
        try:
            log_sent(mentee_email, mentee_name, subject, body)
        except Exception:
            # don't break sending if logging fails
            pass
        return True
        
    except KeyError as e:
        # Bu hata, template dosyasında (örn: {isim} gibi) eksik bir değişken olduğunda oluşur.
        print(f"Hata: {mentee_name} için e-posta oluşturulamadı. Template hatası: {e} değişkeni bulunamadı.")
        # log failure
        subj = locals().get('subject', '')
        bod = locals().get('body', '')
        try:
            log_failed(mentee_email, mentee_name, subj, bod, f"template KeyError: {e}")
        except Exception:
            pass
    except smtplib.SMTPException as e:
        print(f"Error: Unable to send email to {mentee_name}. Reason: {e}")
        subj = locals().get('subject', '')
        bod = locals().get('body', '')
        try:
            log_failed(mentee_email, mentee_name, subj, bod, f"SMTPException: {e}")
        except Exception:
            pass
    except Exception as e:
        print(f"An unexpected error occurred for {mentee_name}: {e}")
        subj = locals().get('subject', '')
        bod = locals().get('body', '')
        try:
            log_failed(mentee_email, mentee_name, subj, bod, f"Exception: {e}")
        except Exception:
            pass


def main():
    """
    Main function to get credentials, read CSV, and loop through mentees.
    This version reads credentials, subject, and template from files.
    """
    
    # Parse command-line args (minimal)
    parser = argparse.ArgumentParser(description='Send personalized emails')
    parser.add_argument('--dry-run', action='store_true', help='Format and print messages without sending')
    args = parser.parse_args()
    dry_run = args.dry_run

    # Load credentials (optional for dry-run), subject, and template
    sender_email, sender_password = load_credentials()
    subject_template = load_text_file(SUBJECT_FILE_NAME)
    body_template = load_text_file(TEMPLATE_FILE_NAME)

    # If templates are missing, stop the script
    if not all([subject_template, body_template]):
        print("Program durduruluyor. Lütfen eksik dosyaları veya hataları kontrol edin.")
        sys.exit(1) # Stop script with an error code

    # For dry-run, we allow missing credentials; substitute a placeholder sender if needed
    if dry_run and not sender_email:
        sender_email = 'no-reply@example.com'

    # If sending for real, ensure credentials are present
    if (not dry_run) and (not all([sender_email, sender_password])):
        print("Program durduruluyor. Lütfen eksik dosyaları veya hataları kontrol edin.")
        sys.exit(1)

    print("\nStarting email process... (dry-run=" + str(dry_run) + ")")

    # Ensure log files exist with headers
    ensure_log_file(LOG_SENT_FILE, ['timestamp','recipient_email','recipient_name','subject','body'])
    ensure_log_file(LOG_FAILED_FILE, ['timestamp','recipient_email','recipient_name','subject','body','reason'])

    # Open the CSV file and either run in dry-run (no SMTP) or real send mode
    try:
        with open(CSV_FILE_NAME, mode='r', encoding='utf-8') as file:
            sample = file.read(2048)
            file.seek(0)
            try:
                has_header = csv.Sniffer().has_header(sample)
            except Exception:
                has_header = False

            if has_header:
                csv_reader = csv.DictReader(file)
            else:
                fieldnames = ['Mentee Ad-Soyad','E-Posta Adresi','Mentör Ad-Soyad','LinkedIn','E-Posta','Telefon Numarası']
                csv_reader = csv.DictReader(file, fieldnames=fieldnames)

            total = 0
            sent = 0
            skipped = 0

            if dry_run:
                # Dry-run: format and print messages without SMTP
                for row in csv_reader:
                    total += 1
                    try:
                        # Try to build subject/body similarly to send_personalized_email
                        mentee_name = row.get('Mentee Ad-Soyad')
                        mentee_email = row.get('E-Posta Adresi')
                        mentor_name = row.get('Mentör Ad-Soyad')

                        mentor_linkedin = row.get('LinkedIn') if row.get('LinkedIn') != '-' else 'Belirtilmedi'
                        mentor_email = row.get('E-Posta') if row.get('E-Posta') != '-' else 'Belirtilmedi'
                        mentor_phone = row.get('Telefon Numarası') if row.get('Telefon Numarası') != '-' else 'Belirtilmedi'

                        # Use safe_format (but capture escaped version for debugging if needed)
                        try:
                            subject = safe_format(subject_template, {
                                'mentee_name': mentee_name,
                                'mentor_name': mentor_name,
                            })
                        except Exception as e:
                            s_sub = subject_template.replace('{', '{{').replace('}', '}}')
                            for k in ('mentee_name','mentor_name'):
                                s_sub = s_sub.replace('{{' + k + '}}', '{' + k + '}')
                            print(f"DRY-RUN: Failed formatting subject; escaped preview:\n{s_sub[:400]}")
                            raise

                        try:
                            body = safe_format(body_template, {
                                'mentee_name': mentee_name,
                                'mentor_name': mentor_name,
                                'mentor_linkedin': mentor_linkedin,
                                'mentor_email': mentor_email,
                                'mentor_phone': mentor_phone,
                                'sender_name': SENDER_NAME,
                                'SENDER_NAME': SENDER_NAME,
                            })
                        except Exception as e:
                            s_body = body_template.replace('{', '{{').replace('}', '}}')
                            for k in ('mentee_name','mentor_name','mentor_linkedin','mentor_email','mentor_phone','sender_name','SENDER_NAME'):
                                s_body = s_body.replace('{{' + k + '}}', '{' + k + '}')
                            print(f"DRY-RUN: Failed formatting body; escaped preview:\n{s_body[:400]}")
                            raise

                        if not mentee_email:
                            print(f"DRY-RUN: Skipping row #{total} - no recipient email: {row}")
                            log_failed(mentee_email, mentee_name, '', '', 'no recipient email')
                            skipped += 1
                            continue

                        print(f"\n--- DRY-RUN Message #{total} ---")
                        print(f"To: {mentee_email}")
                        print(f"Subject: {subject}")
                        print("Body preview:")
                        print(body[:500])
                        # Log as 'sent' in dry-run (formatted)
                        log_sent(mentee_email, mentee_name, subject, body)
                        sent += 1

                    except Exception as e:
                        print(f"DRY-RUN Error formatting row #{total}: {e}")
                        skipped += 1

                print(f"\nDRY-RUN CSV rows processed: {total}, messages formatted: {sent}, skipped: {skipped}")
            else:
                # Real send path: connect to SMTP and send messages
                context = ssl.create_default_context()
                try:
                    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context) as server:
                        server.login(sender_email, sender_password)
                        print("Login successful. Starting to send emails...")

                        for row in csv_reader:
                            total += 1
                            try:
                                ok = send_personalized_email(
                                    server,
                                    sender_email,
                                    row,
                                    subject_template,
                                    body_template
                                )
                                if ok:
                                    # send_personalized_email will log the sent entry
                                    sent += 1
                                else:
                                    # send_personalized_email should have logged the failure
                                    skipped += 1
                            except Exception as e:
                                print(f"Error sending to row #{total}: {e}")
                                skipped += 1

                        print(f"\nCSV rows processed: {total}, sent: {sent}, skipped: {skipped}")
                except smtplib.SMTPAuthenticationError:
                    print("\n--- CRITICAL ERROR ---")
                    print("Login failed. Program stopped.")
                    print(f"Please check your email and password in '{CONFIG_FILE_NAME}'.")

    except FileNotFoundError:
        print(f"Error: The file '{CSV_FILE_NAME}' was not found.")
        print("Please make sure the CSV file is in the same directory as the script.")
    except Exception as e:
        print(f"An unexpected critical error occurred: {e}")

    print("\nEmail process finished.")


# Run the main function when the script is executed
if __name__ == "__main__":
    main()