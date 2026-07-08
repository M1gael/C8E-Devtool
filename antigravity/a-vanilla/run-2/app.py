from tina4_python.dotenv import load_env
load_env()

import threading
import time
from tina4_python.core.events import emit

def fire_ready():
    time.sleep(1.0)  # Wait for framework and routes to initialize
    emit("app.ready", {})

threading.Thread(target=fire_ready, daemon=True).start()

from tina4_python.core import run

run()
