# Automated Mailer

A small Python utility to send personalized, HTML email notifications to mentees. The script reads a CSV of matches, formats an HTML template and subject (from `subject.txt`), and sends messages via SMTP. Includes a safe dry-run mode so you can preview messages without sending, and fallbacks to handle CSVs with or without headers.

## Features

- CSV-driven mail-merge (supports headered and headerless CSVs)
- HTML templates with placeholders: `{mentee_name}`, `{mentor_name}`, `{mentor_linkedin}`, `{mentor_email}`, `{mentor_phone}`, `{SENDER_NAME}`
- Safe dry-run mode: preview formatted messages with `--dry-run`
- Minimal, single-file script (no heavy dependencies)
- Simple SMTP login using `config.txt` (email + app password)

## Quickstart

Requirements: Python 3.8+

1. Put sender credentials into `config.txt` (first line = sender email, second line = app password)
2. Edit `subject.txt` and `email_template.html` with placeholders
3. Prepare `test.csv` (or `mentorluk kabul son.csv`) — add header if needed:

```
Mentee Ad-Soyad,E-Posta Adresi,Mentör Ad-Soyad,LinkedIn,E-Posta,Telefon Numarası
```

4. Preview messages (no send):

```powershell
python auto_mailv2.py --dry-run
```

5. Send messages (uses `config.txt` credentials):

```powershell
python auto_mailv2.py
```

## Security & privacy

- Do NOT commit `config.txt` or CSV files with real participant data. These are included in `.gitignore` by default.
- For Gmail, create an App Password and use that rather than your primary account password.

## Notes

- The script includes heuristics to handle CSVs that lack exact headers, and a safe template formatter that avoids interpreting CSS braces as format placeholders.

## Logging

The script will create two runtime CSV logs in the working directory (these files are ignored by Git by default):

- `sent_emails.csv` — appended for each message formatted/sent. Columns:
	1. timestamp (UTC, ISO format)
 2. recipient_email
 3. recipient_name
 4. subject
 5. body (full rendered HTML/text)

- `failed_emails.csv` — appended for each failed or skipped message. Columns:
	1. timestamp (UTC, ISO format)
 2. recipient_email
 3. recipient_name
 4. subject
 5. body
 6. reason (error message or reason for skip)

These files are added to `.gitignore` to avoid accidental commits of participant data.

## License

MIT
