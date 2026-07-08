import os
from datetime import datetime

def send_receipt_email(data: dict):
    """Logs the borrowing receipt email to data/emails.log.
    
    Expected keys:
    - member_email: Email of the borrower
    - member_name: Name of the borrower
    - book_title: Title of the borrowed book
    - due_date: Due date of the loan
    """
    member_email = data.get("member_email", "unknown@example.com")
    member_name = data.get("member_name", "Unknown Member")
    book_title = data.get("book_title", "Unknown Book")
    due_date = data.get("due_date", "Unknown Due Date")
    
    log_dir = "data"
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "emails.log")
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    email_content = (
        f"==================================================\n"
        f"Timestamp: {timestamp}\n"
        f"To: {member_name} <{member_email}>\n"
        f"Subject: Lend Library — Borrowing Receipt\n"
        f"--------------------------------------------------\n"
        f"Dear {member_name},\n\n"
        f"You have successfully borrowed '{book_title}' from the Lend Library.\n"
        f"Please return it by the due date: {due_date}.\n\n"
        f"Thank you for being part of our community library!\n"
        f"==================================================\n\n"
    )
    
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(email_content)
    
    # Print to console for server logs
    print(f"[MAIL QUEUE WORKER] Sent borrowing receipt for '{book_title}' to {member_email}")
