"""
ApiProber.discovery.wordlist -- Wordlist-basiertes Probing
============================================================
Testet bekannte API-Pfade gegen den Ziel-Service.
"""
from pathlib import Path


def load_wordlist(wordlist_name):
    """Laedt Pfade aus einer Wordlist-Datei.

    Args:
        wordlist_name: Dateiname (z.B. "common_rest.txt")

    Returns:
        list: Liste von Pfaden
    """
    wordlist_dir = Path(__file__).resolve().parent.parent / "wordlists"
    filepath = wordlist_dir / wordlist_name
    if not filepath.exists():
        return []
    paths = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                paths.append(line)
    return paths


def load_all_wordlists(wordlist_names=None):
    """Laedt alle konfigurierten Wordlists und merged sie.

    Args:
        wordlist_names: Liste von Dateinamen, oder None fuer alle

    Returns:
        list: Deduplizierte Liste von Pfaden
    """
    if wordlist_names is None:
        wordlist_dir = Path(__file__).resolve().parent.parent / "wordlists"
        if wordlist_dir.exists():
            wordlist_names = [f.name for f in wordlist_dir.glob("*.txt")]
        else:
            wordlist_names = []

    seen = set()
    paths = []
    for name in wordlist_names:
        for path in load_wordlist(name):
            if path not in seen:
                seen.add(path)
                paths.append(path)
    return paths


def probe_wordlist(client, base_url, wordlist_names, robots_checker=None,
                   known_paths=None, callback=None, max_requests=None):
    """Testet Wordlist-Pfade gegen einen Service.

    Args:
        client: HttpClient Instanz
        base_url: Basis-URL des Services
        wordlist_names: Liste der zu ladenden Wordlists
        robots_checker: RobotsChecker oder None
        known_paths: Set bereits bekannter Pfade (werden uebersprungen)
        callback: Funktion(path, response) fuer jeden Fund
        max_requests: Maximale Gesamtzahl Requests (Client-zaehler)

    Returns:
        list: [(path, response), ...] fuer erfolgreiche Pfade
    """
    base_url = base_url.rstrip("/")
    paths = load_all_wordlists(wordlist_names)
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

        # HEAD liefert manchmal 405 -- dann GET versuchen
        if resp.status_code == 405:
            resp = client.get(url)

        # Endpoint gefunden (nicht 404, nicht Connection Error)
        if resp.status_code > 0 and resp.status_code != 404:
            results.append((path, resp))
            known.add(path)
            if callback:
                callback(path, resp)

    return results
