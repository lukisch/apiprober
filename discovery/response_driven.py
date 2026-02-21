"""
ApiProber.discovery.response_driven -- HATEOAS / Link-Following
================================================================
Extrahiert Links aus bereits entdeckten Responses und folgt ihnen.
"""
import json
from ..core.schema_extractor import extract_links_from_json


def discover_from_responses(client, base_url, db, service_id,
                            robots_checker=None, known_paths=None,
                            max_depth=2, callback=None):
    """Entdeckt neue Endpoints durch Link-Following.

    Liest bestehende Responses aus der DB, extrahiert Links,
    und testet sie als potentielle Endpoints.

    Args:
        client: HttpClient Instanz
        base_url: Basis-URL
        db: Database Instanz
        service_id: Service-ID
        robots_checker: RobotsChecker oder None
        known_paths: Set bekannter Pfade
        max_depth: Maximale Rekursionstiefe
        callback: Funktion(path, response)

    Returns:
        list: [(path, response), ...]
    """
    base_url = base_url.rstrip("/")
    known = known_paths or set()
    all_results = []

    for depth in range(max_depth):
        new_links = set()

        # Bekannte Endpoints durchgehen und Links aus deren Responses sammeln
        endpoints = db.get_endpoints(service_id)
        for ep in endpoints:
            responses = db.get_responses(ep["id"])
            for resp_row in responses:
                body = resp_row.get("body_sample", "")
                if not body:
                    continue
                try:
                    data = json.loads(body)
                    links = extract_links_from_json(data, base_url)
                    for link in links:
                        # Relative Pfade normalisieren
                        path = _normalize_link(link, base_url)
                        if path and path not in known:
                            new_links.add(path)
                except (json.JSONDecodeError, ValueError):
                    continue

        if not new_links:
            break

        # Neue Links testen
        round_results = []
        for path in sorted(new_links):
            if robots_checker and not robots_checker.is_allowed(path):
                continue

            url = f"{base_url}{path}"
            resp = client.get(url)

            if resp.status_code > 0 and resp.status_code != 404:
                round_results.append((path, resp))
                known.add(path)
                if callback:
                    callback(path, resp)

        all_results.extend(round_results)

        if not round_results:
            break

    return all_results


def _normalize_link(link, base_url):
    """Normalisiert einen Link zu einem relativen Pfad."""
    if link.startswith(base_url):
        link = link[len(base_url):]
    if not link.startswith("/"):
        link = "/" + link
    # Query-Parameter entfernen
    if "?" in link:
        link = link.split("?")[0]
    # Fragment entfernen
    if "#" in link:
        link = link.split("#")[0]
    # Trailing Slash normalisieren
    if link != "/" and link.endswith("/"):
        link = link.rstrip("/")
    return link if link else None
