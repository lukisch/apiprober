"""
ApiProber.core.schema_extractor -- JSON-Schema aus Responses ableiten
======================================================================
Analysiert Response-Bodies und generiert ein kompaktes JSON-Schema.
"""
import json


def extract_schema(data):
    """Leitet ein JSON-Schema aus einem Python-Objekt ab.

    Args:
        data: Parsed JSON (dict, list, str, int, float, bool, None)

    Returns:
        dict: Kompaktes JSON-Schema-aehnliches Objekt
    """
    if data is None:
        return {"type": "null"}
    elif isinstance(data, bool):
        return {"type": "boolean"}
    elif isinstance(data, int):
        return {"type": "integer"}
    elif isinstance(data, float):
        return {"type": "number"}
    elif isinstance(data, str):
        schema = {"type": "string"}
        if len(data) > 0:
            schema["example_length"] = len(data)
        return schema
    elif isinstance(data, list):
        schema = {"type": "array", "length": len(data)}
        if len(data) > 0:
            # Schema des ersten Elements als Repraesentation
            schema["items"] = extract_schema(data[0])
        return schema
    elif isinstance(data, dict):
        properties = {}
        for key, value in data.items():
            properties[key] = extract_schema(value)
        return {
            "type": "object",
            "properties": properties,
            "field_count": len(properties)
        }
    else:
        return {"type": "unknown"}


def extract_schema_from_body(body_str):
    """Versucht JSON-Schema aus einem Response-Body zu extrahieren.

    Args:
        body_str: Raw response body als String

    Returns:
        dict: Schema oder leeres dict bei Fehler
    """
    if not body_str or not body_str.strip():
        return {}
    try:
        data = json.loads(body_str)
        return extract_schema(data)
    except (json.JSONDecodeError, ValueError):
        return {}


def extract_links_from_json(data, base_url=""):
    """Extrahiert URL-aehnliche Werte aus einem JSON-Objekt (HATEOAS).

    Args:
        data: Parsed JSON
        base_url: Basis-URL fuer relative Pfade

    Returns:
        set: Gefundene URLs/Pfade
    """
    links = set()
    _walk_for_links(data, links, base_url)
    return links


def _walk_for_links(data, links, base_url):
    """Rekursiv nach URLs in JSON suchen."""
    if isinstance(data, str):
        # Absolute URLs
        if data.startswith("http://") or data.startswith("https://"):
            if base_url and data.startswith(base_url):
                links.add(data)
        # Relative API-Pfade
        elif data.startswith("/") and not data.startswith("//"):
            links.add(data)
    elif isinstance(data, dict):
        # HATEOAS-typische Keys
        for key in ("href", "url", "link", "self", "next", "prev",
                     "first", "last", "related"):
            if key in data:
                _walk_for_links(data[key], links, base_url)
        # _links Objekt (HAL)
        if "_links" in data:
            _walk_for_links(data["_links"], links, base_url)
        # Alle Werte rekursiv
        for value in data.values():
            _walk_for_links(value, links, base_url)
    elif isinstance(data, list):
        for item in data[:50]:  # Max 50 Elemente traversieren
            _walk_for_links(item, links, base_url)


def extract_params_from_error(body_str):
    """Versucht Parameter-Hinweise aus Fehlermeldungen zu extrahieren.

    Viele APIs geben bei fehlenden Parametern Hinweise wie:
    "missing required field: email" oder "field 'name' is required"

    Returns:
        list: [(param_name, required_bool), ...]
    """
    params = []
    if not body_str:
        return params

    import re

    # Patterns fuer Parameter-Hinweise in Error-Messages
    patterns = [
        r"(?:missing|required)\s+(?:field|param(?:eter)?)[:\s]+['\"]?(\w+)['\"]?",
        r"['\"](\w+)['\"]\s+(?:is|are)\s+required",
        r"(?:field|param(?:eter)?)\s+['\"](\w+)['\"]\s+(?:is\s+)?(?:missing|required)",
        r"expected\s+['\"](\w+)['\"]",
    ]

    for pattern in patterns:
        matches = re.findall(pattern, body_str, re.IGNORECASE)
        for match in matches:
            if match and len(match) > 1:
                params.append((match, True))

    return params
