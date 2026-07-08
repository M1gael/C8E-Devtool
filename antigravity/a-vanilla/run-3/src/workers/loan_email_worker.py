import time
from tina4_python.queue import Queue
from tina4_python.messenger import create_messenger
from tina4_python.debug import Log

class LoanEmailWorker:
    def __init__(self):
        self.queue = Queue(topic="loans_email", max_retries=3)
        self._running = False

    def run(self):
        self._running = True
        Log.info("Loan email worker started")

        while self._running:
            job = self.queue.pop()

            if job is None:
                # Sleep briefly if no jobs
                time.sleep(1)
                continue

            try:
                self._send_receipt(job.payload)
                job.complete()
                Log.info("Loan email receipt sent successfully", to=job.payload.get("member_email"))
            except Exception as exc:
                job.fail(str(exc))
                Log.warning("Loan email receipt failed, retrying...", to=job.payload.get("member_email"), error=str(exc))

    def stop(self):
        self._running = False
        Log.info("Loan email worker stopped")

    def _send_receipt(self, payload):
        mailer = create_messenger()
        
        # HTML layout for receipt
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px; color: #333;">
            <h2 style="color: #4f46e5;">Lend Library — Loan Receipt</h2>
            <p>Hello <strong>{payload['member_name']}</strong>,</p>
            <p>This is your borrowing receipt for the following book:</p>
            <div style="background-color: #f3f4f6; padding: 15px; border-radius: 8px; margin: 15px 0;">
                <p style="margin: 5px 0;"><strong>Book Title:</strong> {payload['book_title']}</p>
                <p style="margin: 5px 0;"><strong>Borrow Date:</strong> {payload['borrow_date']}</p>
                <p style="margin: 5px 0; color: #dc2626;"><strong>Due Date:</strong> {payload['due_date']}</p>
            </div>
            <p>Please ensure the book is returned on or before the due date to avoid any penalties.</p>
            <p>Thank you for using Lend!</p>
            <hr style="border: 0; border-top: 1px solid #e5e7eb; margin-top: 20px;">
            <p style="font-size: 12px; color: #9ca3af;">This is an automated email. Please do not reply directly to this message.</p>
        </body>
        </html>
        """
        
        result = mailer.send(
            to=payload["member_email"],
            subject=f"Receipt for borrowing '{payload['book_title']}'",
            body=html_body,
            html=True
        )
        if not result["success"]:
            raise Exception(result["error"])
