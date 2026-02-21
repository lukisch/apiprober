"""
ApiProber.core.http_client -- HTTP-Client mit Rate-Limiting
=============================================================
urllib.request Wrapper mit Auth, Rate-Limiting, User-Agent.
Pattern: BACH connectors/base.py (dataclass, UA, Retry)
"""
import json
import time
import ssl
import urllib.request
import urllib.error
import urllib.parse
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class HttpResponse:
    """Ergebnis eines HTTP-Requests."""
    url: str
    method: str
    status_code: int
    headers: dict = field(default_factory=dict)
    body: str = ""
    content_type: str = ""
    elapsed_ms: int = 0
    error: str = ""
    is_json: bool = False

    @property
    def ok(self):
        return 200 <= self.status_code < 400

    def json(self):
        if self.body:
            return json.loads(self.body)
        return None


class HttpClient:
    """HTTP-Client mit Rate-Limiting und Auth-Support."""

    def __init__(self, config):
        self.delay_ms = config.get("delay_ms", 500)
        self.timeout = config.get("timeout_seconds", 15)
        self.user_agent = config.get("user_agent", "ApiProber/0.1")
        self.auth_type = config.get("auth", {}).get("type", "none")
        self.auth_value = config.get("auth", {}).get("value", "")
        self._last_request_time = 0.0
        self._request_count = 0
        self._ssl_ctx = ssl.create_default_context()

    @property
    def request_count(self):
        return self._request_count

    def request(self, url, method="GET", body=None, extra_headers=None):
        """HTTP-Request mit Rate-Limiting. Gibt HttpResponse zurueck."""
        self._rate_limit()

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json, text/html, */*",
        }

        # Auth
        if self.auth_type == "bearer" and self.auth_value:
            headers["Authorization"] = f"Bearer {self.auth_value}"
        elif self.auth_type == "api_key" and self.auth_value:
            headers["X-API-Key"] = self.auth_value
        elif self.auth_type == "basic" and self.auth_value:
            import base64
            encoded = base64.b64encode(self.auth_value.encode()).decode()
            headers["Authorization"] = f"Basic {encoded}"

        if extra_headers:
            headers.update(extra_headers)

        data = None
        if body is not None:
            if isinstance(body, dict):
                data = json.dumps(body).encode("utf-8")
                headers["Content-Type"] = "application/json"
            elif isinstance(body, str):
                data = body.encode("utf-8")
            elif isinstance(body, bytes):
                data = body

        req = urllib.request.Request(url, data=data, headers=headers, method=method)

        start = time.monotonic()
        self._request_count += 1

        try:
            with urllib.request.urlopen(req, timeout=self.timeout,
                                        context=self._ssl_ctx) as resp:
                elapsed = int((time.monotonic() - start) * 1000)
                resp_headers = dict(resp.headers)
                content_type = resp_headers.get("Content-Type", "")
                raw_body = resp.read()

                # Body decodieren
                body_str = ""
                try:
                    body_str = raw_body.decode("utf-8")
                except UnicodeDecodeError:
                    body_str = raw_body.decode("latin-1", errors="replace")

                is_json = "json" in content_type.lower()

                return HttpResponse(
                    url=url, method=method,
                    status_code=resp.status,
                    headers=resp_headers,
                    body=body_str,
                    content_type=content_type,
                    elapsed_ms=elapsed,
                    is_json=is_json
                )
        except urllib.error.HTTPError as e:
            elapsed = int((time.monotonic() - start) * 1000)
            resp_headers = dict(e.headers) if e.headers else {}
            content_type = resp_headers.get("Content-Type", "")
            body_str = ""
            try:
                raw = e.read()
                body_str = raw.decode("utf-8", errors="replace")
            except Exception:
                pass
            return HttpResponse(
                url=url, method=method,
                status_code=e.code,
                headers=resp_headers,
                body=body_str,
                content_type=content_type,
                elapsed_ms=elapsed,
                error=str(e),
                is_json="json" in content_type.lower()
            )
        except urllib.error.URLError as e:
            elapsed = int((time.monotonic() - start) * 1000)
            return HttpResponse(
                url=url, method=method,
                status_code=0,
                elapsed_ms=elapsed,
                error=str(e.reason)
            )
        except Exception as e:
            elapsed = int((time.monotonic() - start) * 1000)
            return HttpResponse(
                url=url, method=method,
                status_code=0,
                elapsed_ms=elapsed,
                error=str(e)
            )

    def head(self, url):
        return self.request(url, method="HEAD")

    def get(self, url):
        return self.request(url, method="GET")

    def options(self, url):
        return self.request(url, method="OPTIONS")

    def _rate_limit(self):
        """Wartet bis delay_ms seit letztem Request vergangen sind."""
        if self._last_request_time > 0:
            elapsed = (time.monotonic() - self._last_request_time) * 1000
            remaining = self.delay_ms - elapsed
            if remaining > 0:
                time.sleep(remaining / 1000.0)
        self._last_request_time = time.monotonic()
