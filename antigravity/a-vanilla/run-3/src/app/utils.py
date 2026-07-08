from tina4_python.i18n import I18n
from tina4_python.auth import Auth

def render_template(request, response, template_name, data=None):
    """Renders a Twig template with request-scoped localized translations and session state."""
    if data is None:
        data = {}
    
    # Manage language switcher (query parameter overrides session)
    lang = request.params.get("lang")
    if lang in ("en", "es"):
        request.session.set("lang", lang)
    
    current_lang = request.session.get("lang", "en")
    
    # Initialize translation helper for the request
    i18n = I18n(locale=current_lang)
    
    # Expose variables and translation function to Twig
    data["t"] = i18n.t
    data["current_lang"] = current_lang
    data["session"] = request.session.all()
    
    # Extract flash notifications
    data["flash_success"] = request.session.flash("success")
    data["flash_error"] = request.session.flash("error")
    
    return response.render(template_name, data)

def get_current_user(request):
    """Retrieves the authenticated staff user payload from headers or session."""
    # 1. Check API token in headers
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        payload = Auth.valid_token_static(token)
        if payload:
            return payload
            
    # 2. Check session token/user
    session = getattr(request, "session", None)
    if session:
        session_token = session.get("token")
        if session_token:
            payload = Auth.valid_token_static(session_token)
            if payload:
                return payload
        user = session.get("user")
        if user:
            return user
            
    return None
