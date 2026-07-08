from tina4_python.core import run
from tina4_python.database import Database
from tina4_python.orm import bind_database
from tina4_python.migration import migrate
from tina4_python.core.server import background
from tina4_python.queue import Queue

# 1. Initialize and bind database
db = Database()
bind_database(db)

# 2. Run pending migrations on startup
try:
    migrate(db)
except Exception as e:
    print(f"Migration error during startup: {e}")

# 3. Define and register background queue email consumer
def consume_emails():
    try:
        queue = Queue(topic="emails")
        while True:
            job = queue.pop()
            if job is None:
                break
            try:
                # Import dynamically to avoid circular import issues
                from src.app.mail import send_receipt_email
                send_receipt_email(job.data)
                job.complete()
            except Exception as job_err:
                job.fail(str(job_err))
                print(f"Error processing email job: {job_err}")
    except Exception as q_err:
        print(f"Queue consumer error: {q_err}")

# Poll the email queue every 2 seconds cooperatively
background(consume_emails, 2.0)

if __name__ == "__main__":
    run()
