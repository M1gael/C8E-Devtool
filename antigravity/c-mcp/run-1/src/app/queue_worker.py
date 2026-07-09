import os
from datetime import datetime
from tina4_python.queue import Queue

async def poll_email_queue():
    """
    Polls the database/file-backed 'emails' queue topic and processes any pending
    borrowing receipt jobs asynchronously.
    """
    queue = Queue(topic="emails")
    
    # Process all available queued items
    while True:
        job = queue.pop()
        if job is None:
            break
            
        try:
            data = job.data
            email = data.get("email")
            member_name = data.get("member_name")
            book_title = data.get("book_title")
            due_date = data.get("due_date")
            
            # Formulate the receipt
            receipt = (
                f"[{datetime.now().isoformat()}] EMAIL RECEIPT SENT TO: {email}\n"
                f"Dear {member_name},\n"
                f"Thank you for borrowing '{book_title}'.\n"
                f"Please note that it is due on: {due_date}.\n"
                f"----------------------------------------\n"
            )
            
            # Append receipt to receipts.log
            log_path = os.path.join(os.getcwd(), "receipts.log")
            with open(log_path, "a", encoding="utf-8") as fh:
                fh.write(receipt)
                
            print(f"Queue Worker: Asynchronously sent borrow receipt to {email} for book '{book_title}'.")
            
            # Confirm completion
            job.complete()
        except Exception as e:
            print(f"Queue Worker Error: Failed to process receipt job: {e}")
            job.fail(str(e))
