"""
ApiProber.discovery.orchestrator -- Zentrale Steuerung aller Strategien
========================================================================
Koordiniert OpenAPI-Detection, Wordlist, Pattern und Response-Driven.
"""
import json
import sys
from pathlib import Path

from ..core.config import load_config, get_db_path
from ..core.database import Database
from ..core.http_client import HttpClient
from ..core.robots import RobotsChecker
from ..core.schema_extractor import extract_schema_from_body, extract_params_from_error
from .openapi_detect import detect_openapi, extract_endpoints_from_spec
from .wordlist import probe_wordlist
from .pattern import probe_patterns
from .response_driven import discover_from_responses
from .method_tester import test_methods


class ProbeOrchestrator:
    """Orchestriert den gesamten Probing-Vorgang."""

    def __init__(self, config=None):
        self.config = config or load_config()
        self.db = Database(get_db_path(self.config))
        self.client = HttpClient(self.config)
        self._stop_requested = False

    def probe(self, url, depth=None):
        """Hauptmethode: Vollstaendiges Probing eines Service.

        Args:
            url: Basis-URL des zu probenden Service
            depth: Maximale Rekursionstiefe (ueberschreibt Config)

        Returns:
            dict: Zusammenfassung der Ergebnisse
        """
        if depth is not None:
            self.config["max_depth"] = depth

        base_url = url.rstrip("/")
        service_name = self._derive_service_name(base_url)
        max_requests = self.config.get("max_requests", 500)
        skip_destructive = self.config.get("skip_destructive", True)

        print(f"[ApiProber] Starte Probing: {base_url}")
        print(f"  Service-Name: {service_name}")
        print(f"  Max Requests: {max_requests}")
        print(f"  Delay: {self.config.get('delay_ms', 500)}ms")
        print(f"  Destructive: {'Nein' if skip_destructive else 'Ja'}")
        print()

        # 1. Service in DB anlegen
        service_id = self.db.upsert_service(service_name, base_url)
        run_id = self.db.create_probe_run(service_id, self.config)
        known_paths = self.db.get_endpoint_paths(service_id)
        endpoints_found = 0

        # 2. robots.txt laden
        robots = None
        if self.config.get("respect_robots_txt", True):
            robots = RobotsChecker(base_url, self.config.get("user_agent", ""))
            success, raw = robots.load()
            if success:
                self.db.upsert_service(service_name, base_url, robots_txt=raw)
                print(f"  robots.txt: Geladen ({len(raw)} Bytes)")
                crawl_delay = robots.crawl_delay
                if crawl_delay:
                    effective_delay = max(self.config["delay_ms"], int(crawl_delay * 1000))
                    self.client.delay_ms = effective_delay
                    print(f"  Crawl-Delay: {crawl_delay}s (effektiv: {effective_delay}ms)")
            else:
                print("  robots.txt: Nicht vorhanden (alles erlaubt)")
            print()

        # 3. Base-URL testen
        print("[Phase 0] Base-URL testen...")
        base_resp = self.client.get(base_url)
        if base_resp.status_code > 0:
            server = base_resp.headers.get("Server", "")
            if server:
                self.db.upsert_service(service_name, base_url, server_header=server)
                print(f"  Server: {server}")
            print(f"  Status: {base_resp.status_code}")
            print(f"  Content-Type: {base_resp.content_type}")
        else:
            print(f"  FEHLER: {base_resp.error}")
            self.db.update_probe_run(run_id, status="error")
            return {"error": base_resp.error}
        print()

        # Callback fuer Endpoint-Verarbeitung
        def on_endpoint_found(path, resp):
            nonlocal endpoints_found
            endpoints_found += 1
            status_char = "+" if resp.ok else "~"
            print(f"  [{status_char}] {path} -> {resp.status_code}")

        strategies = self.config.get("strategies", ["openapi", "wordlist", "pattern", "response_driven"])

        # 4. OpenAPI-Detection (Prio 1)
        if "openapi" in strategies and not self._check_limits(max_requests):
            print("[Phase 1] OpenAPI/Swagger Detection...")
            spec_url, spec = detect_openapi(self.client, base_url, robots)
            if spec:
                print(f"  GEFUNDEN: {spec_url}")
                spec_endpoints = extract_endpoints_from_spec(spec)
                print(f"  {len(spec_endpoints)} Endpoints in Spec")
                for ep in spec_endpoints:
                    ep_id = self.db.upsert_endpoint(
                        service_id, ep["path"],
                        methods=ep["methods"],
                        discovered_by="openapi"
                    )
                    known_paths.add(ep["path"])
                    endpoints_found += 1
                    # Parameter speichern
                    for param in ep.get("parameters", []):
                        self.db.upsert_parameter(
                            ep_id,
                            name=param["name"],
                            param_type=param.get("type", "string"),
                            location=param.get("location", "query"),
                            required=param.get("required", False)
                        )
                # Spec als Metadata speichern
                meta = {"openapi_spec_url": spec_url}
                if "info" in spec:
                    meta["api_title"] = spec["info"].get("title", "")
                    meta["api_version"] = spec["info"].get("version", "")
                    meta["api_description"] = spec["info"].get("description", "")
                self.db.upsert_service(service_name, base_url, metadata=meta)
            else:
                print("  Keine OpenAPI/Swagger-Spec gefunden")
            print()

        # 5. Wordlist-Probing (Prio 2)
        if "wordlist" in strategies and not self._check_limits(max_requests):
            print("[Phase 2] Wordlist-Probing...")
            wordlist_names = self.config.get("wordlists", [])
            results = probe_wordlist(
                self.client, base_url, wordlist_names,
                robots_checker=robots, known_paths=known_paths,
                callback=on_endpoint_found, max_requests=max_requests
            )
            self._process_results(service_id, results, "wordlist")
            print(f"  {len(results)} neue Endpoints entdeckt")
            print()

        # 6. Pattern-Probing (Prio 3)
        if "pattern" in strategies and not self._check_limits(max_requests):
            print("[Phase 3] Pattern-Probing...")
            results = probe_patterns(
                self.client, base_url, self.config,
                robots_checker=robots, known_paths=known_paths,
                callback=on_endpoint_found, max_requests=max_requests
            )
            self._process_results(service_id, results, "pattern")
            print(f"  {len(results)} neue Endpoints entdeckt")
            print()

        # 7. Method-Testing fuer entdeckte Endpoints
        if not self._check_limits(max_requests):
            print("[Phase 4] Method-Testing...")
            endpoints = self.db.get_endpoints(service_id)
            tested = 0
            for ep in endpoints:
                if self._check_limits(max_requests):
                    break
                method_info = test_methods(
                    self.client, base_url, ep["path"],
                    skip_destructive=skip_destructive
                )
                self.db.upsert_endpoint(
                    service_id, ep["path"],
                    methods=method_info["methods"],
                    status_codes=list(method_info["status_codes"].values()),
                    auth_required=method_info["auth_required"],
                    auth_type_hint=method_info["auth_type_hint"],
                    content_types=method_info["content_types"]
                )
                tested += 1
            print(f"  {tested} Endpoints getestet")
            print()

        # 8. Detaillierte GET-Responses fuer Schema-Extraktion
        if not self._check_limits(max_requests):
            print("[Phase 5] Schema-Extraktion...")
            endpoints = self.db.get_endpoints(service_id)
            schemas_extracted = 0
            for ep in endpoints:
                if self._check_limits(max_requests):
                    break
                methods = json.loads(ep.get("methods_json", "[]"))
                if "GET" not in methods:
                    continue
                url = f"{base_url}{ep['path']}"
                resp = self.client.get(url)
                if resp.ok and resp.body:
                    schema = extract_schema_from_body(resp.body)
                    if schema:
                        self.db.add_response(
                            ep["id"], "GET", resp.status_code,
                            headers=resp.headers,
                            body_schema=schema,
                            body_sample=resp.body[:2048],
                            content_type=resp.content_type,
                            elapsed_ms=resp.elapsed_ms
                        )
                        schemas_extracted += 1
                elif resp.status_code in (400, 422) and resp.body:
                    # Parameter-Hints aus Error-Body
                    params = extract_params_from_error(resp.body)
                    for name, required in params:
                        self.db.upsert_parameter(
                            ep["id"], name, required=required
                        )
            print(f"  {schemas_extracted} Schemas extrahiert")
            print()

        # 9. Response-Driven Discovery (Prio 4)
        if "response_driven" in strategies and not self._check_limits(max_requests):
            print("[Phase 6] Response-Driven Discovery (HATEOAS)...")
            results = discover_from_responses(
                self.client, base_url, self.db, service_id,
                robots_checker=robots, known_paths=known_paths,
                max_depth=self.config.get("max_depth", 2),
                callback=on_endpoint_found
            )
            self._process_results(service_id, results, "response_driven")
            print(f"  {len(results)} neue Endpoints entdeckt")
            print()

        # 10. Abschluss
        self.db.update_service_last_probed(service_id)
        total_requests = self.client.request_count
        final_ep_count = len(self.db.get_endpoints(service_id))

        self.db.update_probe_run(
            run_id,
            status="completed",
            total_requests=total_requests,
            endpoints_found=final_ep_count,
            progress={"completed_strategies": strategies}
        )

        summary = {
            "service": service_name,
            "base_url": base_url,
            "endpoints_found": final_ep_count,
            "total_requests": total_requests,
            "status": "completed"
        }

        print("=" * 60)
        print(f"[Ergebnis] {service_name}")
        print(f"  Endpoints entdeckt: {final_ep_count}")
        print(f"  Requests gesamt:    {total_requests}")
        print(f"  DB: {self.db.db_path}")
        print("=" * 60)

        return summary

    def resume(self, service_name):
        """Setzt ein vorheriges Probing fort.

        Laedt den letzten unvollstaendigen Run und macht weiter.
        """
        service = self.db.get_service(service_name)
        if not service:
            print(f"Service '{service_name}' nicht gefunden.")
            return None

        last_run = self.db.get_last_probe_run(service["id"])
        if not last_run:
            print(f"Kein vorheriger Run fuer '{service_name}'.")
            return None

        if last_run["status"] == "completed":
            print(f"Letzter Run bereits abgeschlossen. Starte neuen Probe.")

        # Config aus letztem Run laden
        try:
            run_config = json.loads(last_run.get("config_json", "{}"))
            if run_config:
                self.config.update(run_config)
        except (json.JSONDecodeError, ValueError):
            pass

        return self.probe(service["base_url"])

    def _process_results(self, service_id, results, discovered_by):
        """Verarbeitet Probe-Ergebnisse in die DB."""
        for path, resp in results:
            content_types = []
            if resp.content_type:
                ct = resp.content_type.split(";")[0].strip()
                if ct:
                    content_types = [ct]

            auth_required = resp.status_code in (401, 403)
            auth_hint = ""
            if auth_required:
                www_auth = resp.headers.get("WWW-Authenticate", "")
                if "bearer" in www_auth.lower():
                    auth_hint = "bearer"
                elif "basic" in www_auth.lower():
                    auth_hint = "basic"

            ep_id = self.db.upsert_endpoint(
                service_id, path,
                methods=[resp.method] if resp.method else [],
                status_codes=[resp.status_code],
                auth_required=auth_required,
                auth_type_hint=auth_hint,
                content_types=content_types,
                discovered_by=discovered_by
            )

            # Response speichern wenn Body vorhanden
            if resp.body and resp.ok:
                schema = extract_schema_from_body(resp.body)
                self.db.add_response(
                    ep_id, resp.method or "GET", resp.status_code,
                    headers=resp.headers,
                    body_schema=schema,
                    body_sample=resp.body[:2048],
                    content_type=resp.content_type,
                    elapsed_ms=resp.elapsed_ms
                )

    def _check_limits(self, max_requests):
        """Prueft ob Request-Limit erreicht ist."""
        if self.client.request_count >= max_requests:
            print(f"  [LIMIT] Max Requests erreicht ({max_requests})")
            return True
        # STOP-Datei pruefen
        stop_file = Path(__file__).resolve().parent.parent / "STOP"
        if stop_file.exists():
            print("  [STOP] STOP-Datei gefunden -- Abbruch")
            return True
        return False

    def _derive_service_name(self, url):
        """Leitet einen Service-Namen aus der URL ab."""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        host = parsed.hostname or "unknown"
        # Subdomains entfernen fuer kurzen Namen
        parts = host.split(".")
        if len(parts) >= 2:
            name = parts[-2]  # z.B. "jsonplaceholder" aus "jsonplaceholder.typicode.com"
        else:
            name = host
        return name
