from django.utils import translation


class LanguageMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        first = request.path.strip("/").split("/")[0]
        request.LANGUAGE_CODE = first if first in {"de", "en"} else "de"
        with translation.override(request.LANGUAGE_CODE):
            response = self.get_response(request)
        response.headers["Content-Language"] = request.LANGUAGE_CODE
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self'; img-src 'self' data:; "
            "script-src 'none'; base-uri 'none'; object-src 'none'; frame-ancestors 'none'; form-action 'self'"
        )
        if request.path not in {"/", "/de/", "/en/"}:
            response.headers["Cache-Control"] = "private, no-store"
            response.headers["X-Robots-Tag"] = "noindex, nofollow"
        return response
