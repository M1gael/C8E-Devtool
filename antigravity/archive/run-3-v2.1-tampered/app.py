from tina4_python.core import run
from tina4_python.service import ServiceRunner
from src.workers.loan_email_worker import LoanEmailWorker
import atexit

# Start background email worker
runner = ServiceRunner()
runner.register("loan_email_worker", LoanEmailWorker())
runner.start()

# Register shutdown hook
atexit.register(runner.stop)

run()
