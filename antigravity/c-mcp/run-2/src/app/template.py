from tina4_python.core.response import get_frond
from tina4_python.i18n import I18n

# Initialize the global i18n instance
i18n = I18n(locale_dir="src/locales", default_locale="en")

# Define the translation helper
def translate(key, **kwargs):
    # Perform translation lookup
    return i18n.t(key, **kwargs)

# Register translation helper as a global function and filter in the Frond engine
get_frond().add_global("t", translate)
get_frond().add_filter("t", translate)

def render(template_name, data=None, request=None):
    """
    Renders a Twig/Frond template with data and request context.
    Injects default variables like session, language, and request query.
    """
    if data is None:
        data = {}
    
    if request:
        data["session"] = request.session
        # Determine language (priority: session > query parameter > default "en")
        lang = "en"
        if hasattr(request, "session") and request.session:
            lang = request.session.get("lang") or "en"
        
        # Override language if present in query parameters
        if hasattr(request, "query") and "lang" in request.query:
            lang = request.query["lang"]
            if hasattr(request, "session") and request.session:
                request.session.set("lang", lang)
        
        data["lang"] = lang
        data["query"] = request.query
        data["url"] = request.url
        
        # Set active locale on i18n instance so nested t() calls inside template render using this locale
        i18n.locale = lang

    return get_frond().render(template_name, data)
