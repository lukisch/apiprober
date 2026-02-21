"""
ApiProber.export.markdown -- Markdown-Export aus DB
====================================================
Generiert lesbare API-Dokumentation als .md-Datei.
"""
import json
from pathlib import Path
from datetime import datetime


def export_markdown(db, service, output_path):
    """Exportiert Service-Doku als Markdown.

    Args:
        db: Database Instanz
        service: Service-dict aus DB
        output_path: Ziel-Pfad fuer .md-Datei
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    endpoints = db.get_endpoints(service["id"])
    stats = db.get_service_stats(service["id"])
    runs = db.get_probe_runs(service["id"])

    lines = []

    # Header
    lines.append(f"# API-Dokumentation: {service['name']}")
    lines.append("")
    lines.append(f"**Base-URL:** `{service['base_url']}`")
    if service.get("server_header"):
        lines.append(f"**Server:** `{service['server_header']}`")
    if service.get("description"):
        lines.append(f"**Beschreibung:** {service['description']}")
    lines.append(f"**Entdeckt:** {service.get('discovered_at', '-')}")
    lines.append(f"**Letztes Probing:** {service.get('last_probed', '-')}")
    lines.append("")

    # Metadata
    meta = {}
    try:
        meta = json.loads(service.get("metadata_json", "{}"))
    except (json.JSONDecodeError, ValueError):
        pass
    if meta.get("api_title"):
        lines.append(f"**API-Titel:** {meta['api_title']}")
    if meta.get("api_version"):
        lines.append(f"**API-Version:** {meta['api_version']}")
    if meta.get("api_description"):
        lines.append(f"**API-Beschreibung:** {meta['api_description']}")
    if meta:
        lines.append("")

    # Statistiken
    lines.append("## Ueberblick")
    lines.append("")
    lines.append(f"| Metrik | Wert |")
    lines.append(f"|--------|------|")
    lines.append(f"| Endpoints | {stats['endpoints']} |")
    lines.append(f"| Responses | {stats['responses']} |")
    lines.append(f"| Parameter | {stats['parameters']} |")
    lines.append(f"| Probe-Runs | {len(runs)} |")
    lines.append("")

    # Endpoints
    if endpoints:
        lines.append("## Endpoints")
        lines.append("")

        # Uebersichtstabelle
        lines.append("| Pfad | Methoden | Auth | Entdeckt durch |")
        lines.append("|------|----------|------|----------------|")
        for ep in endpoints:
            methods = json.loads(ep.get("methods_json", "[]"))
            methods_str = ", ".join(methods) if methods else "?"
            auth = "Ja" if ep.get("auth_required") else "Nein"
            by = ep.get("discovered_by", "-")
            lines.append(f"| `{ep['path']}` | {methods_str} | {auth} | {by} |")
        lines.append("")

        # Detail-Sektionen
        for ep in endpoints:
            methods = json.loads(ep.get("methods_json", "[]"))
            methods_str = ", ".join(methods) if methods else "?"
            lines.append(f"### `{ep['path']}`")
            lines.append("")
            lines.append(f"**Methoden:** {methods_str}")

            status_codes = json.loads(ep.get("status_codes_json", "[]"))
            if status_codes:
                lines.append(f"**Status-Codes:** {', '.join(str(c) for c in status_codes)}")

            content_types = json.loads(ep.get("content_types_json", "[]"))
            if content_types:
                lines.append(f"**Content-Types:** {', '.join(content_types)}")

            if ep.get("auth_required"):
                hint = ep.get("auth_type_hint", "unbekannt")
                lines.append(f"**Auth erforderlich:** Ja ({hint})")

            # Parameter
            params = db.get_parameters(ep["id"])
            if params:
                lines.append("")
                lines.append("**Parameter:**")
                lines.append("")
                lines.append("| Name | Typ | Location | Required | Beispiel |")
                lines.append("|------|-----|----------|----------|----------|")
                for p in params:
                    req = "Ja" if p.get("required") else "Nein"
                    example = p.get("example_value", "-") or "-"
                    lines.append(
                        f"| `{p['name']}` | {p.get('param_type', 'string')} "
                        f"| {p.get('location', 'query')} | {req} | {example} |"
                    )

            # Responses
            responses = db.get_responses(ep["id"])
            if responses:
                lines.append("")
                lines.append("**Responses:**")
                for resp in responses:
                    lines.append("")
                    lines.append(f"- **{resp['method']} {resp['status_code']}** "
                                f"({resp.get('content_type', '-')}), {resp.get('elapsed_ms', 0)}ms")

                    # Schema anzeigen
                    schema = {}
                    try:
                        schema = json.loads(resp.get("body_schema_json", "{}"))
                    except (json.JSONDecodeError, ValueError):
                        pass
                    if schema:
                        lines.append("")
                        lines.append("  Schema:")
                        lines.append("  ```json")
                        lines.append(f"  {json.dumps(schema, indent=2, ensure_ascii=False)}")
                        lines.append("  ```")

            lines.append("")

    # Probe-Runs
    if runs:
        lines.append("## Probe-Runs")
        lines.append("")
        lines.append("| # | Gestartet | Status | Requests | Endpoints |")
        lines.append("|---|-----------|--------|----------|-----------|")
        for run in runs:
            started = run.get("started_at", "-")
            if started and len(started) > 16:
                started = started[:16]
            lines.append(
                f"| {run['id']} | {started} | {run.get('status', '-')} "
                f"| {run.get('total_requests', 0)} | {run.get('endpoints_found', 0)} |"
            )
        lines.append("")

    # Footer
    lines.append("---")
    lines.append(f"*Generiert von ApiProber v0.1.0 am {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}*")
    lines.append("")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
