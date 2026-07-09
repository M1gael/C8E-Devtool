from tina4_python.core import run
from src.app.email_worker import start_email_worker
import src.app.template  # Registers i18n globals and filters

# Start background email queue worker
start_email_worker()

# Run the Tina4 framework
run()
