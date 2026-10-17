"""Small stateless login for the shared HTTPS hackathon demo."""

import base64
import binascii
import hashlib
import hmac
import secrets
import time

from fastapi.responses import HTMLResponse

SESSION_COOKIE = "arsia_demo"
SESSION_SECONDS = 8 * 60 * 60


def _key(settings):
    material = settings.origin_token + "\x00" + settings.demo_username + "\x00" + settings.demo_password
    return hmac.new(material.encode(), b"arsia-demo-session-v1", hashlib.sha256).digest()


def session_token(settings, now=None):
    expiry = int(time.time() if now is None else now) + SESSION_SECONDS
    payload = f"v1:{expiry}:{secrets.token_urlsafe(18)}".encode()
    encoded = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    signature = hmac.new(_key(settings), encoded.encode(), hashlib.sha256).hexdigest()
    return encoded + "." + signature


def valid_session(token, settings, now=None):
    if not token or len(token) > 512:
        return False
    try:
        encoded, signature = token.split(".")
        expected = hmac.new(_key(settings), encoded.encode(), hashlib.sha256).hexdigest()
        if not secrets.compare_digest(signature.encode(), expected.encode()):
            return False
        payload = base64.b64decode(encoded + "=" * (-len(encoded) % 4), altchars=b"-_", validate=True).decode("ascii")
        version, expiry_text, nonce = payload.split(":")
        current = int(time.time() if now is None else now)
        return version == "v1" and bool(nonce) and current < int(expiry_text) <= current + SESSION_SECONDS
    except (ValueError, UnicodeError, binascii.Error):
        return False


def valid_credentials(username, password, settings):
    if not isinstance(username, str) or not isinstance(password, str) or len(username) > 128 or len(password) > 512:
        return False
    correct_user = secrets.compare_digest(username.encode(), settings.demo_username.encode())
    correct_password = secrets.compare_digest(password.encode(), settings.demo_password.encode())
    return correct_user and correct_password


def login_page(error=False):
    message = '<p class="error" role="alert">The sign-in details were not recognized.</p>' if error else ""
    html = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Sign in · Arsia</title>
<style>*{box-sizing:border-box}body{margin:0;background:#fff;color:#17202e;font:15px system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}main{width:min(360px,calc(100% - 48px));margin:16vh auto}h1{font-size:32px;font-weight:600;letter-spacing:-1px;margin:0 0 8px}p{color:#697282;margin:0 0 36px}label{display:block;font-size:13px;font-weight:500;margin:20px 0 8px}input,button{width:100%;font:inherit;border-radius:7px}input{padding:12px;border:1px solid #d7dce3;background:#fff}input:focus{outline:2px solid #1d56d3;outline-offset:2px}button{margin-top:28px;padding:12px;border:0;color:#fff;background:#1d56d3;cursor:pointer}button:hover{background:#1746ae}.error{margin:22px 0 0;color:#a22c2c;line-height:1.5}</style></head>
<body><main><h1>Arsia</h1><p>Annual Review Agent</p><form method="post" action="/login"><label for="username">Username</label><input id="username" name="username" autocomplete="username" maxlength="128" required autofocus><label for="password">Password</label><input id="password" name="password" type="password" autocomplete="current-password" maxlength="512" required><button type="submit">Sign in</button>""" + message + "</form></main></body></html>"
    return HTMLResponse(html, status_code=401 if error else 200, headers={
        "Cache-Control": "no-store", "Referrer-Policy": "same-origin", "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'",
    })
