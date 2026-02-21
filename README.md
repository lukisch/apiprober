# ApiProber -- Systematic API Discovery Tool

Probe undocumented or poorly documented APIs. Discover endpoints through
trial-and-error, map API structures, store results in SQLite, and generate
documentation.

**Author:** Lukas Geiger | **License:** MIT | **Python:** 3.8+ (stdlib only)

---

## Features

- **Multi-Strategy Discovery:** OpenAPI detection, wordlist probing, pattern expansion, HATEOAS link following
- **Rate Limiting:** Configurable delay between requests (default: 500ms)
- **robots.txt Compliance:** Automatic respect for access restrictions
- **Auth Support:** Bearer token, API key, Basic auth
- **JSON Schema Extraction:** Automatic schema inference from response bodies
- **SQLite Persistence:** All results stored in a local database
- **Export:** Markdown and JSON (OpenAPI-like)
- **Resume:** Continue interrupted probing sessions
- **Ethical by Default:** Only passive exploration, no fuzzing or destructive methods
- **Zero Dependencies:** Pure Python stdlib (urllib, json, sqlite3, argparse, pathlib)

---

## Installation

No installation required -- works with Python 3.8+ standard library only.

```bash
git clone https://github.com/lukisch/apiprober.git
cd apiprober

# Run directly
python -m ApiProber --help

# Or install as package
pip install -e .
apiprober --help
```

---

## Quick Start

### Probe an API

```bash
# Basic probe
python -m ApiProber probe https://jsonplaceholder.typicode.com

# Deep probe with custom delay
python -m ApiProber probe https://api.example.com --depth 2 --delay-ms 1000

# Authenticated probe
python -m ApiProber probe https://api.example.com --auth-type bearer --auth-value "YOUR_TOKEN"
```

### Manage Services

```bash
# List all probed services
python -m ApiProber list

# Show details for a specific service
python -m ApiProber status jsonplaceholder

# Resume interrupted probing
python -m ApiProber resume jsonplaceholder
```

### Export Results

```bash
# Export as Markdown documentation
python -m ApiProber export jsonplaceholder --format md

# Export as JSON (OpenAPI-like)
python -m ApiProber export jsonplaceholder --format json
```

### Configuration

```bash
# Show current config
python -m ApiProber config --show

# Set values
python -m ApiProber config --set delay_ms 1000
python -m ApiProber config --set auth.type bearer
```

---

## Discovery Strategies

ApiProber uses four strategies in priority order:

1. **OpenAPI Detection** (Priority 1): Checks for `/swagger.json`, `/openapi.json`, `/api-docs`, etc.
2. **Wordlist Probing** (Priority 2): Tests ~140 common REST endpoint paths
3. **Pattern Expansion** (Priority 3): Expands `/api/v{1,2,3}/{resource}` patterns
4. **Response-Driven / HATEOAS** (Priority 4): Follows links discovered in response bodies

---

## Security and Ethics

ApiProber is designed for responsible API exploration:

- **Default: Read-only** -- Only GET, HEAD, OPTIONS (no POST/PUT/DELETE unless `--test-all-methods` flag)
- **Built-in rate limiting** -- Configurable delay between requests
- **robots.txt compliance** -- Automatically respects access restrictions
- **Transparent User-Agent** -- `ApiProber/0.1 (github.com/lukisch; passive-discovery)`
- **No fuzzing, no exploitation** -- Purely passive discovery

---

## Project Structure

```
ApiProber/
+-- api_prober.py        CLI entry point
+-- config.json          Default configuration
+-- core/                Core modules
|   +-- config.py        Configuration management
|   +-- database.py      SQLite persistence layer
|   +-- http_client.py   HTTP client with rate limiting
|   +-- robots.py        robots.txt parser
|   +-- schema_extractor.py  JSON schema inference
+-- discovery/           Discovery strategies
|   +-- orchestrator.py  Strategy coordination
|   +-- openapi_detect.py  OpenAPI/Swagger detection
|   +-- wordlist.py      Wordlist-based probing
|   +-- pattern.py       Pattern expansion
|   +-- response_driven.py  HATEOAS link following
|   +-- method_tester.py  HTTP method testing
+-- export/              Export formats
|   +-- json_export.py   JSON export
|   +-- markdown.py      Markdown documentation generator
+-- wordlists/           Probe wordlists (~140 paths)
|   +-- common_rest.txt  Common REST endpoints
|   +-- admin_paths.txt  Admin/management paths
|   +-- auth_endpoints.txt  Authentication endpoints
|   +-- swagger_paths.txt  Swagger/OpenAPI paths
+-- data/                Runtime data (api_prober.db) -- gitignored
+-- exports/             Generated documentation -- gitignored
```

---

## Use Cases

- **Reverse engineering** undocumented internal APIs
- **Validating** API documentation against actual behavior
- **Discovering** hidden endpoints in third-party services
- **Generating** API documentation for legacy systems
- **Security auditing** (passive reconnaissance only)

---

## License

MIT License. See [LICENSE](LICENSE).

---

## Author

Lukas Geiger -- [github.com/lukisch](https://github.com/lukisch)
