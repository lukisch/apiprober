"""
ApiProber.discovery.pattern -- Pattern-basiertes Probing
==========================================================
Expandiert Pfad-Patterns wie /api/v{1,2,3}/{resource}.
"""


def generate_patterns(config):
    """Generiert Pfade aus Pattern-Expansion.

    Args:
        config: Konfiguration mit pattern_versions und pattern_resources

    Returns:
        list: Expandierte Pfade
    """
    versions = config.get("pattern_versions", [1, 2, 3])
    resources = config.get("pattern_resources", [
        "users", "posts", "comments", "items", "products"
    ])

    paths = set()

    # /api/v{N}/{resource}
    for v in versions:
        for res in resources:
            paths.add(f"/api/v{v}/{res}")

    # /v{N}/{resource}
    for v in versions:
        for res in resources:
            paths.add(f"/v{v}/{res}")

    # /{resource} (ohne Version)
    for res in resources:
        paths.add(f"/{res}")

    # /{resource}/1 (Einzelressource-Test)
    for res in resources:
        paths.add(f"/{res}/1")

    # /api/{resource}
    for res in resources:
        paths.add(f"/api/{res}")

    return sorted(paths)


def probe_patterns(client, base_url, config, robots_checker=None,
                   known_paths=None, callback=None, max_requests=None):
    """Testet Pattern-generierte Pfade.

    Args:
        client: HttpClient Instanz
        base_url: Basis-URL
        config: Konfiguration
        robots_checker: RobotsChecker oder None
        known_paths: Set bereits bekannter Pfade
        callback: Funktion(path, response) bei Fund
        max_requests: Maximale Gesamtzahl Requests (Client-zaehler)

    Returns:
        list: [(path, response), ...]
    """
    base_url = base_url.rstrip("/")
    paths = generate_patterns(config)
    known = known_paths or set()
    results = []

    for path in paths:
        if max_requests and client.request_count >= max_requests:
            break
        if path in known:
            continue
        if robots_checker and not robots_checker.is_allowed(path):
            continue

        url = f"{base_url}{path}"
        resp = client.head(url)

        if resp.status_code == 405:
            resp = client.get(url)

        if resp.status_code > 0 and resp.status_code != 404:
            results.append((path, resp))
            known.add(path)
            if callback:
                callback(path, resp)

    return results
