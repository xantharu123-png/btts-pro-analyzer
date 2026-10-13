"""Real subprocess transport used by Bash-stdin test harnesses."""
import locale
import subprocess
import sys


def run_bash_lf(*args, **kwargs):
    """Keep script bytes exact; restore only subprocess's output text API."""
    text = kwargs.pop("text", None)
    universal = kwargs.pop("universal_newlines", None)
    encoding = kwargs.pop("encoding", None)
    errors = kwargs.pop("errors", None)
    if text is not None and universal is not None and bool(text) != bool(universal):
        raise ValueError("text and universal_newlines must agree")
    text_output = bool(text or universal or encoding or errors)
    if isinstance(kwargs.get("input"), str):
        # Never normalize caller-supplied CR/LF or bytes. Windows TextIOWrapper
        # must not silently change the Bash program submitted on stdin.
        kwargs["input"] = kwargs["input"].encode("utf-8")
    encoding = encoding or ("utf-8" if sys.flags.utf8_mode else locale.getencoding())
    errors = errors or "strict"

    def decoded(value):
        if value is None:
            return None
        return value.decode(encoding, errors).replace("\r\n", "\n").replace("\r", "\n")

    try:
        result = subprocess.run(*args, **kwargs)
    except subprocess.CalledProcessError as error:
        if text_output:
            error.stdout, error.stderr = decoded(error.stdout), decoded(error.stderr)
        raise
    if text_output:
        result.stdout, result.stderr = decoded(result.stdout), decoded(result.stderr)
    return result
