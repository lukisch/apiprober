"""
ApiProber.export.json_export -- JSON-Export (OpenAPI-aehnlich)
===============================================================
Exportiert entdeckte API-Struktur als JSON.
"""
import json
from pathlib import Path
from datetime import datetime


def export_json(db, service, output_path):
    """Exportiert Service als strukturiertes JSON.

    Args:
        db: Database Instanz
        service: Service-dict aus DB
        output_path: Ziel-Pfad fuer .json-Datei
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    endpoints = db.get_endpoints(service["id"])
    stats = db.get_service_stats(service["id"])

    # Metadata parsen
    meta = {}
    try:
        meta = json.loads(service.get("metadata_json", "{}"))
    except (json.JSONDecodeError, ValueError):
        pass

    # Endpoints aufbauen
    paths = {}
    for ep in endpoints:
        methods = json.loads(ep.get("methods_json", "[]"))
        status_codes = json.loads(ep.get("status_codes_json", "[]"))
        content_types = json.loads(ep.get("content_types_json", "[]"))

        path_info = {
            "methods": methods,
            "status_codes": status_codes,
            "content_types": content_types,
            "auth_required": bool(ep.get("auth_required")),
            "auth_type_hint": ep.get("auth_type_hint", ""),
            "discovered_by": ep.get("discovered_by", ""),
        }

        # Parameter
        params = db.get_parameters(ep["id"])
        if params:
            path_info["parameters"] = [
                {
                    "name": p["name"],
                    "type": p.get("param_type", "string"),
                    "location": p.get("location", "query"),
                    "required": bool(p.get("required")),
                    "example": p.get("example_value", "")
                }
                for p in params
            ]

        # Responses
        responses = db.get_responses(ep["id"])
        if responses:
            path_info["responses"] = []
            for resp in responses:
                resp_info = {
                    "method": resp["method"],
                    "status_code": resp["status_code"],
                    "content_type": resp.get("content_type", ""),
                    "elapsed_ms": resp.get("elapsed_ms", 0),
                }
                try:
                    schema = json.loads(resp.get("body_schema_json", "{}"))
                    if schema:
                        resp_info["schema"] = schema
                except (json.JSONDecodeError, ValueError):
                    pass
                path_info["responses"].append(resp_info)

        paths[ep["path"]] = path_info

    # Gesamtstruktur
    export_data = {
        "apiprober_version": "0.1.0",
        "exported_at": datetime.utcnow().isoformat(),
        "service": {
            "name": service["name"],
            "base_url": service["base_url"],
            "description": service.get("description", ""),
            "server_header": service.get("server_header", ""),
            "discovered_at": service.get("discovered_at", ""),
            "last_probed": service.get("last_probed", ""),
            "metadata": meta,
        },
        "statistics": stats,
        "paths": paths,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(export_data, f, indent=2, ensure_ascii=False)
