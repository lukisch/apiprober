#!/usr/bin/env python3
"""
ApiProber -- Systematisches API-Probing fuer undokumentierte Services
======================================================================
CLI Entry Point mit argparse Subcommands.
Pattern: llmauto/llmauto.py (argparse + func-Dispatch)

Verwendung:
    python api_prober.py probe <url> [--depth N] [--delay-ms N] [--auth-type TYPE] [--auth-value VALUE]
    python api_prober.py list
    python api_prober.py status <service>
    python api_prober.py export <service> [--format md|json]
    python api_prober.py resume <service>
    python api_prober.py config [--show | --set KEY VALUE]
"""
import argparse
import json
import sys
from pathlib import Path

# Sicherstellen dass das Paket importierbar ist
PACKAGE_DIR = Path(__file__).resolve().parent
_parent = str(PACKAGE_DIR.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

VERSION = "0.1.0"


def cmd_probe(args):
    """Probe-Modus: API abtasten."""
    from ApiProber.core.config import load_config
    from ApiProber.discovery.orchestrator import ProbeOrchestrator

    config = load_config()

    # CLI-Overrides
    if args.depth is not None:
        config["max_depth"] = args.depth
    if args.delay_ms is not None:
        config["delay_ms"] = args.delay_ms
    if args.max_requests is not None:
        config["max_requests"] = args.max_requests
    if args.auth_type:
        config["auth"]["type"] = args.auth_type
    if args.auth_value:
        config["auth"]["value"] = args.auth_value
    if args.test_all_methods:
        config["skip_destructive"] = False

    orchestrator = ProbeOrchestrator(config)
    result = orchestrator.probe(args.url, depth=args.depth)

    if result and result.get("error"):
        return 1
    return 0


def cmd_list(args):
    """Alle bekannten Services auflisten."""
    from ApiProber.core.config import get_db_path, load_config
    from ApiProber.core.database import Database

    config = load_config()
    db_path = get_db_path(config)
    if not db_path.exists():
        print("Keine Datenbank vorhanden. Starte zuerst ein Probing.")
        return 0

    db = Database(db_path)
    services = db.list_services()

    if not services:
        print("Keine Services gespeichert.")
        return 0

    print(f"{'Name':<25} {'Base-URL':<45} {'Endpoints':<10} {'Letztes Probing'}")
    print("-" * 95)
    for svc in services:
        stats = db.get_service_stats(svc["id"])
        last = svc.get("last_probed", "-") or "-"
        if last and len(last) > 16:
            last = last[:16]
        print(f"{svc['name']:<25} {svc['base_url']:<45} {stats['endpoints']:<10} {last}")

    return 0


def cmd_status(args):
    """Status eines Services anzeigen."""
    from ApiProber.core.config import get_db_path, load_config
    from ApiProber.core.database import Database

    config = load_config()
    db = Database(get_db_path(config))

    service = db.get_service(args.service)
    if not service:
        print(f"Service '{args.service}' nicht gefunden.")
        return 1

    stats = db.get_service_stats(service["id"])
    endpoints = db.get_endpoints(service["id"])
    runs = db.get_probe_runs(service["id"])

    print(f"Service: {service['name']}")
    print(f"URL:     {service['base_url']}")
    print(f"Server:  {service.get('server_header', '-')}")
    print(f"Entdeckt:  {service.get('discovered_at', '-')}")
    print(f"Letztes Probing: {service.get('last_probed', '-')}")
    print()
    print(f"Endpoints:  {stats['endpoints']}")
    print(f"Responses:  {stats['responses']}")
    print(f"Parameter:  {stats['parameters']}")
    print(f"Probe-Runs: {len(runs)}")
    print()

    if endpoints:
        print("Endpoints:")
        for ep in endpoints:
            methods = json.loads(ep.get("methods_json", "[]"))
            auth = " [AUTH]" if ep.get("auth_required") else ""
            print(f"  {', '.join(methods) if methods else '?':<30} {ep['path']}{auth}")

    return 0


def cmd_export(args):
    """Export der Ergebnisse."""
    from ApiProber.core.config import get_db_path, get_export_dir, load_config
    from ApiProber.core.database import Database

    config = load_config()
    db = Database(get_db_path(config))

    service = db.get_service(args.service)
    if not service:
        print(f"Service '{args.service}' nicht gefunden.")
        return 1

    export_dir = get_export_dir(config)
    export_dir.mkdir(parents=True, exist_ok=True)

    fmt = args.format or "md"

    if fmt == "md":
        from ApiProber.export.markdown import export_markdown
        output_path = export_dir / f"{service['name']}_api.md"
        export_markdown(db, service, output_path)
        print(f"Markdown exportiert: {output_path}")

    elif fmt == "json":
        from ApiProber.export.json_export import export_json
        output_path = export_dir / f"{service['name']}_api.json"
        export_json(db, service, output_path)
        print(f"JSON exportiert: {output_path}")

    elif fmt == "pdf":
        from ApiProber.export.markdown import export_markdown
        md_path = export_dir / f"{service['name']}_api.md"
        export_markdown(db, service, md_path)
        print(f"Markdown erstellt: {md_path}")
        print("PDF-Generierung: Nutze cc_md_to_pdf oder fc_md_to_pdf MCP-Tool.")

    else:
        print(f"Unbekanntes Format: {fmt}")
        return 1

    return 0


def cmd_resume(args):
    """Vorheriges Probing fortsetzen."""
    from ApiProber.core.config import load_config
    from ApiProber.discovery.orchestrator import ProbeOrchestrator

    config = load_config()
    orchestrator = ProbeOrchestrator(config)
    result = orchestrator.resume(args.service)

    if result is None:
        return 1
    return 0


def cmd_config(args):
    """Konfiguration anzeigen oder setzen."""
    from ApiProber.core.config import load_config, save_config

    config = load_config()

    if args.show:
        print(json.dumps(config, indent=4, ensure_ascii=False))
        return 0

    if args.key and args.value:
        key = args.key
        value = args.value

        # Typ-Konvertierung
        if value.lower() in ("true", "false"):
            value = value.lower() == "true"
        elif value.isdigit():
            value = int(value)
        else:
            try:
                value = float(value)
            except ValueError:
                pass  # bleibt String

        # Verschachtelte Keys mit Punkt-Notation
        keys = key.split(".")
        target = config
        for k in keys[:-1]:
            if k not in target or not isinstance(target[k], dict):
                target[k] = {}
            target = target[k]
        target[keys[-1]] = value

        save_config(config)
        print(f"Gesetzt: {key} = {value}")
        return 0

    print("Verwendung: config --show | config --set KEY VALUE")
    return 0


def main():
    parser = argparse.ArgumentParser(
        prog="api_prober",
        description="ApiProber -- Systematisches API-Probing fuer undokumentierte Services",
    )
    parser.add_argument("--version", "-V", action="store_true", help="Version anzeigen")
    subparsers = parser.add_subparsers(dest="command")

    # --- probe ---
    probe_parser = subparsers.add_parser("probe", help="API abtasten")
    probe_parser.add_argument("url", help="Basis-URL des Service")
    probe_parser.add_argument("--depth", type=int, default=None, help="Maximale Tiefe (default: 3)")
    probe_parser.add_argument("--delay-ms", type=int, default=None, help="Delay zwischen Requests in ms")
    probe_parser.add_argument("--max-requests", type=int, default=None, help="Maximale Anzahl Requests")
    probe_parser.add_argument("--auth-type", choices=["bearer", "api_key", "basic"], help="Auth-Typ")
    probe_parser.add_argument("--auth-value", help="Auth-Wert (Token, Key, user:pass)")
    probe_parser.add_argument("--test-all-methods", action="store_true",
                              help="Auch POST/PUT/PATCH/DELETE testen (default: nur GET/HEAD/OPTIONS)")
    probe_parser.set_defaults(func=cmd_probe)

    # --- list ---
    list_parser = subparsers.add_parser("list", help="Alle Services auflisten")
    list_parser.set_defaults(func=cmd_list)

    # --- status ---
    status_parser = subparsers.add_parser("status", help="Service-Status anzeigen")
    status_parser.add_argument("service", help="Service-Name")
    status_parser.set_defaults(func=cmd_status)

    # --- export ---
    export_parser = subparsers.add_parser("export", help="Ergebnisse exportieren")
    export_parser.add_argument("service", help="Service-Name")
    export_parser.add_argument("--format", "-f", choices=["md", "json", "pdf"], default="md",
                               help="Export-Format (default: md)")
    export_parser.set_defaults(func=cmd_export)

    # --- resume ---
    resume_parser = subparsers.add_parser("resume", help="Probing fortsetzen")
    resume_parser.add_argument("service", help="Service-Name")
    resume_parser.set_defaults(func=cmd_resume)

    # --- config ---
    config_parser = subparsers.add_parser("config", help="Konfiguration verwalten")
    config_parser.add_argument("--show", action="store_true", help="Aktuelle Konfiguration anzeigen")
    config_parser.add_argument("--set", nargs=2, metavar=("KEY", "VALUE"), dest="key_value",
                               help="Konfigurationswert setzen")
    config_parser.set_defaults(func=cmd_config)

    # Parsen
    args = parser.parse_args()

    if args.version:
        print(f"ApiProber v{VERSION}")
        return 0

    if not args.command:
        parser.print_help()
        return 0

    # config --set braucht Sonderbehandlung
    if args.command == "config" and hasattr(args, "key_value") and args.key_value:
        args.key = args.key_value[0]
        args.value = args.key_value[1]
    elif args.command == "config":
        args.key = None
        args.value = None

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
