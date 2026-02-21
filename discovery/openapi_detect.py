"""
ApiProber.discovery.openapi_detect -- OpenAPI/Swagger Detection
================================================================
Sucht nach OpenAPI/Swagger-Spezifikationen und extrahiert Endpoints.
"""
import json


SWAGGER_PATHS = [
    "/swagger.json", "/openapi.json", "/api-docs",
    "/api-docs.json", "/swagger.yaml", "/openapi.yaml",
    "/docs", "/swagger", "/swagger-ui",
    "/api/swagger.json", "/api/openapi.json",
    "/v1/swagger.json", "/v2/swagger.json",
    "/.well-known/openapi",
]


def detect_openapi(client, base_url, robots_checker=None):
    """Versucht eine OpenAPI-Spec zu finden.

    Args:
        client: HttpClient Instanz
        base_url: Basis-URL
        robots_checker: RobotsChecker oder None

    Returns:
        (spec_url, spec_data) oder (None, None) wenn nichts gefunden
    """
    base_url = base_url.rstrip("/")

    for path in SWAGGER_PATHS:
        if robots_checker and not robots_checker.is_allowed(path):
            continue
        url = f"{base_url}{path}"
        resp = client.get(url)
        if resp.ok and resp.body:
            spec = _try_parse_spec(resp.body)
            if spec:
                return url, spec
    return None, None


def extract_endpoints_from_spec(spec):
    """Extrahiert Endpoints aus einer OpenAPI/Swagger-Spec.

    Args:
        spec: Parsed OpenAPI/Swagger dict

    Returns:
        list: [{"path": str, "methods": [str], "description": str, "parameters": [dict]}, ...]
    """
    endpoints = []

    # OpenAPI 3.x
    paths = spec.get("paths", {})
    if not paths and "basePath" in spec:
        paths = spec.get("paths", {})

    base_path = spec.get("basePath", "")

    for path, methods_obj in paths.items():
        if not isinstance(methods_obj, dict):
            continue

        full_path = f"{base_path}{path}" if base_path else path
        methods = []
        description = ""
        parameters = []

        for method in ("get", "head", "post", "put", "patch", "delete", "options"):
            if method in methods_obj:
                methods.append(method.upper())
                op = methods_obj[method]
                if isinstance(op, dict):
                    if not description:
                        description = op.get("summary", op.get("description", ""))
                    # Parameter sammeln
                    for param in op.get("parameters", []):
                        if isinstance(param, dict):
                            parameters.append({
                                "name": param.get("name", ""),
                                "location": param.get("in", "query"),
                                "required": param.get("required", False),
                                "type": param.get("type",
                                         param.get("schema", {}).get("type", "string"))
                            })

        # Top-level Parameters (gelten fuer alle Methoden)
        for param in methods_obj.get("parameters", []):
            if isinstance(param, dict):
                parameters.append({
                    "name": param.get("name", ""),
                    "location": param.get("in", "query"),
                    "required": param.get("required", False),
                    "type": param.get("type",
                             param.get("schema", {}).get("type", "string"))
                })

        if methods:
            endpoints.append({
                "path": full_path,
                "methods": methods,
                "description": description,
                "parameters": _dedupe_params(parameters)
            })

    return endpoints


def _try_parse_spec(body):
    """Versucht Body als OpenAPI/Swagger-Spec zu parsen."""
    try:
        data = json.loads(body)
        # Minimal-Check: hat es "paths" oder "swagger"/"openapi" Key?
        if isinstance(data, dict):
            if "paths" in data or "swagger" in data or "openapi" in data:
                return data
    except (json.JSONDecodeError, ValueError):
        pass
    return None


def _dedupe_params(params):
    """Entfernt Duplikate aus Parameter-Liste."""
    seen = set()
    unique = []
    for p in params:
        key = (p.get("name", ""), p.get("location", ""))
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique
