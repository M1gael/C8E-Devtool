from tina4_python.core import run
from tina4_python.database import Database
from tina4_python.orm import bind_database
from tina4_python.frond import Frond
from tina4_python.i18n import I18n
from tina4_python.core.server import background
from src.app.queue_worker import poll_email_queue

# Initialize Database & ORM
db = Database()
bind_database(db)

# Initialize I18n
i18n = I18n(locale_dir="src/locales", default_locale="en")

# Add dynamic thread-safe translation function as a template global
Frond.add_global("translate", lambda key, lang="en", **kwargs: i18n.translate(key, params=kwargs, locale=lang))

# Add money filter for pricing/formatting
Frond.add_filter("money", lambda v: f"${float(v or 0):,.2f}")

# Register Background Task Queue Poll (runs cooperatively every 1.0s)
background(poll_email_queue, interval=1.0)

if __name__ == "__main__":
    run()
