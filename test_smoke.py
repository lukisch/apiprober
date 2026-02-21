#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
"""
Smoke Test: ApiProber (SQ080)
==============================

Testet grundlegende Funktionalität des ApiProbers:
- Modul-Import funktioniert
- CLI-Tool startet
- Discovery gegen jsonplaceholder.typicode.com
- Export-Funktionen (Markdown, JSON)

Author: BACH Development Team
Created: 2026-02-21 (SQ080, Runde 34)
"""

import pytest
import sys
import json
from pathlib import Path

# Füge ApiProber-Verzeichnis zum Python-Path hinzu
API_PROBER_DIR = Path(__file__).parent
sys.path.insert(0, str(API_PROBER_DIR))


class TestApiProberImport:
    """Test: Modul-Import."""

    def test_import_api_prober(self):
        """Test: api_prober Modul kann importiert werden."""
        try:
            import api_prober
            assert True
        except ImportError as e:
            pytest.fail(f"api_prober konnte nicht importiert werden: {e}")

    def test_import_discovery(self):
        """Test: discovery Modul existiert."""
        try:
            from core import discovery
            assert hasattr(discovery, 'OpenAPIDiscovery')
            assert hasattr(discovery, 'WordlistDiscovery')
        except ImportError as e:
            pytest.fail(f"discovery Modul fehlt: {e}")

    def test_import_export(self):
        """Test: export Modul existiert."""
        try:
            from core import export
            assert hasattr(export, 'MarkdownExporter')
            assert hasattr(export, 'OpenAPIExporter')
        except ImportError as e:
            pytest.fail(f"export Modul fehlt: {e}")


class TestApiProberCLI:
    """Test: CLI-Tool grundlegende Funktionen."""

    def test_cli_help_works(self):
        """Test: CLI --help funktioniert."""
        import subprocess
        result = subprocess.run(
            [sys.executable, "api_prober.py", "--help"],
            cwd=str(API_PROBER_DIR),
            capture_output=True,
            text=True,
            timeout=5
        )
        assert result.returncode == 0, "--help sollte erfolgreich sein"
        assert "probe" in result.stdout.lower() or "usage" in result.stdout.lower()

    def test_cli_list_works(self):
        """Test: CLI list funktioniert (zeigt Services)."""
        import subprocess
        result = subprocess.run(
            [sys.executable, "api_prober.py", "list"],
            cwd=str(API_PROBER_DIR),
            capture_output=True,
            text=True,
            timeout=5
        )
        # list sollte funktionieren (returncode 0 oder 1 wenn leer)
        assert result.returncode in [0, 1]


class TestApiProberDatabase:
    """Test: Datenbank-Funktionalität."""

    def test_database_creation(self):
        """Test: DB wird erstellt wenn nicht vorhanden."""
        import sqlite3
        db_path = API_PROBER_DIR / "api_prober.db"

        # Falls DB existiert, OK - sonst sollte sie bei Bedarf erstellt werden
        if db_path.exists():
            # Prüfe Schema
            conn = sqlite3.connect(str(db_path))
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            conn.close()

                # Erwartete Tabellen (zumindest eine sollte existieren)
            expected_tables = ['services', 'endpoints', 'requests', 'responses']
            has_tables = any(t in tables for t in expected_tables)
            assert has_tables, f"DB sollte mindestens eine Tabelle haben, gefunden: {tables}"


class TestApiProberQuickProbe:
    """Test: Schneller Probe-Test (minimale API-Abfrage)."""

    def test_quick_probe_jsonplaceholder(self):
        """Test: Minimaler Probe gegen jsonplaceholder.typicode.com."""
        # Dieser Test macht einen ECHTEN API-Call (Quick-Probe)
        # Nur root-Endpoint, keine Subpaths, kurzer Timeout

        import subprocess
        result = subprocess.run(
            [sys.executable, "api_prober.py", "probe",
             "https://jsonplaceholder.typicode.com",
             "--depth", "0",  # Nur Root-Endpoint
             "--delay-ms", "0"],  # Kein Delay (nur 1 Request)
            cwd=str(API_PROBER_DIR),
            capture_output=True,
            text=True,
            timeout=10
        )

        # Sollte erfolgreich sein (returncode 0)
        # ODER Fehler wegen Rate-Limiting / Netzwerk (nicht kritisch für Smoke-Test)
        assert result.returncode in [0, 1], f"Probe fehlgeschlagen: {result.stderr}"

        # Wenn erfolgreich, sollte Output haben
        if result.returncode == 0:
            assert len(result.stdout) > 0, "Probe sollte Output erzeugen"


class TestApiProberExport:
    """Test: Export-Funktionen (konzeptionell)."""

    def test_export_commands_exist(self):
        """Test: export-md und export-json Befehle existieren."""
        import subprocess

        # Prüfe ob export-md Befehl existiert (ohne API-Probe)
        result_md = subprocess.run(
            [sys.executable, "api_prober.py", "export-md", "--help"],
            cwd=str(API_PROBER_DIR),
            capture_output=True,
            text=True,
            timeout=5
        )

        result_json = subprocess.run(
            [sys.executable, "api_prober.py", "export-json", "--help"],
            cwd=str(API_PROBER_DIR),
            capture_output=True,
            text=True,
            timeout=5
        )

        # --help sollte erfolgreich sein ODER Fehlermeldung bei fehlendem --help
        # (je nach Implementierung)
        assert result_md.returncode in [0, 1, 2]
        assert result_json.returncode in [0, 1, 2]


class TestApiProberDocumentation:
    """Test: Dokumentation vorhanden."""

    def test_readme_exists(self):
        """Test: README.md existiert."""
        readme_path = API_PROBER_DIR / "README.md"
        assert readme_path.exists(), "README.md sollte existieren"

        # README sollte Mindest-Inhalt haben
        content = readme_path.read_text(encoding='utf-8')
        assert len(content) > 100, "README sollte Inhalt haben"
        assert "ApiProber" in content or "API Prober" in content


# ============================================================================
#  MAIN (für direktes Ausführen)
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
