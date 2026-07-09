import threading
import time
import logging
from tina4_python.queue import Queue
from tina4_python.messenger import Messenger

logger = logging.getLogger("tina4.email_worker")

def send_receipt_email(to_email, subject, body):
    """Sends email via Tina4's Messenger, logging SMTP errors if any."""
    try:
        mail = Messenger()
        res = mail.send(to=to_email, subject=subject, body=body, html=True)
        logger.info(f"Email sent to {to_email}. Result: {res}")
        print(f"[EMAIL WORKER] Email sent to {to_email}. Result: {res}")
    except Exception as e:
        logger.error(f"Failed to send email to {to_email} via SMTP: {e}")
        print(f"[EMAIL WORKER] Failed to send email to {to_email}: {e}")

def email_worker_loop():
    logger.info("Email queue worker thread started.")
    print("[EMAIL WORKER] Thread started. Listening for 'loan_emails' queue...")
    
    # Wait for framework to initialize fully
    time.sleep(2)
    
    while True:
        try:
            queue = Queue(topic="loan_emails")
            while True:
                job = queue.pop()
                if job is None:
                    break
                data = job.data
                to_email = data.get("to")
                subject = data.get("subject")
                body = data.get("body")
                
                print(f"[EMAIL WORKER] Processing job: email to {to_email}")
                send_receipt_email(to_email, subject, body)
                
                job.complete()
        except Exception as e:
            logger.error(f"Error in email worker loop: {e}")
            print(f"[EMAIL WORKER] Error: {e}")
        time.sleep(2)

def start_email_worker():
    t = threading.Thread(target=email_worker_loop, daemon=True)
    t.start()
