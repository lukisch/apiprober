"""
ApiProber.discovery.method_tester -- HTTP-Methoden pro Endpoint testen
=======================================================================
Testet welche HTTP-Methoden ein Endpoint unterstuetzt.
"""


SAFE_METHODS = ["GET", "HEAD", "OPTIONS"]
ALL_METHODS = ["GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH", "DELETE"]


def test_methods(client, base_url, path, skip_destructive=True):
    """Testet alle HTTP-Methoden fuer einen Endpoint.

    Args:
        client: HttpClient Instanz
        base_url: Basis-URL
        path: Endpoint-Pfad
        skip_destructive: True = nur GET/HEAD/OPTIONS

    Returns:
        dict: {
            "methods": [str],           # Unterstuetzte Methoden
            "status_codes": {str: int},  # Methode -> Status
            "auth_required": bool,
            "auth_type_hint": str,
            "allow_header": str,
            "content_types": [str]
        }
    """
    base_url = base_url.rstrip("/")
    url = f"{base_url}{path}"

    methods_to_test = SAFE_METHODS if skip_destructive else ALL_METHODS
    supported = []
    status_codes = {}
    auth_required = False
    auth_type_hint = ""
    allow_header = ""
    content_types = set()

    for method in methods_to_test:
        resp = client.request(url, method=method)

        if resp.status_code == 0:
            continue  # Connection Error

        status_codes[method] = resp.status_code

        # OPTIONS liefert oft Allow-Header
        if method == "OPTIONS" and "Allow" in resp.headers:
            allow_header = resp.headers["Allow"]
            for m in allow_header.replace(" ", "").split(","):
                m = m.strip().upper()
                if m and m not in supported:
                    supported.append(m)

        # Methode ist unterstuetzt wenn nicht 404/405
        if resp.status_code not in (404, 405, 501):
            if method not in supported:
                supported.append(method)

        # Auth-Detection
        if resp.status_code in (401, 403):
            auth_required = True
            www_auth = resp.headers.get("WWW-Authenticate", "")
            if www_auth:
                if "bearer" in www_auth.lower():
                    auth_type_hint = "bearer"
                elif "basic" in www_auth.lower():
                    auth_type_hint = "basic"
                elif "api" in www_auth.lower():
                    auth_type_hint = "api_key"
                else:
                    auth_type_hint = www_auth.split()[0] if www_auth else ""

        # Content-Types sammeln
        if resp.content_type:
            ct = resp.content_type.split(";")[0].strip()
            if ct:
                content_types.add(ct)

    return {
        "methods": sorted(supported),
        "status_codes": status_codes,
        "auth_required": auth_required,
        "auth_type_hint": auth_type_hint,
        "allow_header": allow_header,
        "content_types": sorted(content_types)
    }
