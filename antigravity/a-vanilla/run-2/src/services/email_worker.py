import time
from tina4_python.queue import Queue
from tina4_python.debug import Log
from tina4_python.messenger import Messenger

class EmailWorker:
    def __init__(self):
        self.queue = Queue(topic="emails", max_retries=3)
        self._running = False

    def __call__(self, ctx):
        self.run(ctx)

    def run(self, ctx):
        self._running = True
        Log.info("Email worker started")

        while self._running and not ctx.stop_event.is_set():
            job = self.queue.pop()

            if job is None:
                ctx.stop_event.wait(1)
                continue

            try:
                self._send_email(job.payload)
                job.complete()
                Log.info(f"Email sent successfully to {job.payload.get('to')}")
            except Exception as exc:
                job.fail(str(exc))
                Log.warning(f"Email failed to {job.payload.get('to')}: {exc}")

    def stop(self):
        self._running = False
        Log.info("Email worker stopped")

    def _send_email(self, payload):
        Log.info(f"Sending email receipt to {payload['to']} for book {payload['title']} due on {payload['due_date']}")
        
        # Instantiate Messenger to send the email
        mailer = Messenger()
        mailer.send(
            to=payload["to"],
            subject=payload["subject"],
            body=payload["body"]
        )

