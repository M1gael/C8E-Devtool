from tina4_python.core import run
from tina4_python.database import Database
from tina4_python.orm import bind_database
from tina4_python.frond import Frond
from tina4_python.i18n import I18n
from tina4_python.core.server import background
from tina4_python.queue import Queue
from tina4_python.messenger import create_messenger
from tina4_python.debug import Log

# 1. Database & ORM
# Respect environment database URL, fallback to default sqlite:///data/lend.db
import os
db_url = os.environ.get("TINA4_DATABASE_URL", "sqlite:///data/lend.db")
db = Database(db_url)
bind_database(db)

# 2. i18n Translation Filter
i18n = I18n()

def trans_filter(key, locale="en", **kwargs):
    """Translate key using context locale and kwargs."""
    return i18n.translate(key, kwargs, locale)

Frond.add_filter("trans", trans_filter)

# 3. Background Email Queue Worker
email_queue = Queue(topic="emails")
messenger = create_messenger()

def process_emails():
    """Poll the queue for a borrow receipt and process it."""
    try:
        job = email_queue.pop()
        if job:
            data = job.data
            recipient = data.get("to")
            member_name = data.get("member_name")
            book_title = data.get("book_title")
            due_date = data.get("due_date")
            
            subject = f"Receipt: Borrowed {book_title}"
            body = (
                f"<p>Dear {member_name},</p>"
                f"<p>This email is a receipt confirming that you have borrowed the book <strong>{book_title}</strong>.</p>"
                f"<p><strong>Due Date:</strong> {due_date}</p>"
                f"<p>Thank you for using Lend Library!</p>"
            )
            
            res = messenger.send(
                to=recipient,
                subject=subject,
                body=body,
                html=True
            )
            if res.get("success"):
                Log.info(f"Email receipt sent to {recipient} for '{book_title}' (Message ID: {res.get('message_id')})")
                job.complete()
            else:
                Log.error(f"Failed to send email to {recipient}: {res.get('error')}")
                job.fail(res.get("error"))
    except Exception as e:
        Log.error(f"Error processing email job: {e}")

# Register cooperative background task with the event loop
background(process_emails, 1.0)

if __name__ == "__main__":
    run()
