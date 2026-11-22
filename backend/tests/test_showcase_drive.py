"""Isolated showcase tests. No credentials, network, or database are required."""

from datetime import date
from threading import Event
from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient

from showcase import drive, main
from showcase.tables import SHEETS, TITLES, parse_tables, seed_tables


class CatalogTests(TestCase):
    def test_scope_and_allowlist(self):
        source = object.__new__(drive.GoogleSource)
        source.files = {key: f"configured-{key}" for key in SHEETS}
        source.allowed = {*source.files.values(), "allowed-proof", "allowed-shortcut"}

        def get(url, **params):
            if url.endswith(drive.ROOT):
                return {"mimeType": drive.FOLDER}
            if url.endswith("/files"):
                if drive.ROOT in params["q"]:
                    return {"files": [{"id": "folder-team", "name": "Команда", "mimeType": drive.FOLDER}]}
                self.assertEqual(params["q"], "'folder-team' in parents and trashed = false")
                return {"files": [
                    *({"id": key, "name": TITLES[group], "mimeType": drive.SHEET}
                      for group, key in source.files.items()),
                    {"id": "allowed-proof", "name": "Разрешённый файл", "mimeType": "text/plain",
                     "size": "312", "modifiedTime": "2026-11-22T12:00:00Z"},
                    {"id": "ignored-file", "name": "Скрытый файл", "mimeType": "text/plain"},
                    {"id": "allowed-shortcut", "name": "Ярлык", "mimeType": "application/vnd.google-apps.shortcut"},
                ]}
            for group, key in source.files.items():
                if f"/{key}/" in url:
                    self.assertEqual(params["ranges"], [f"'{name}'!A1:Z1000" for name in SHEETS[group]])
                    return {"valueRanges": [{"values": seed_tables()[name]} for name in SHEETS[group]]}
            self.fail(url)

        source.get = get
        tables, catalog = source.load()
        self.assertEqual(set(tables), {name for names in SHEETS.values() for name in names})
        children = catalog[0]["children"]
        self.assertEqual({entry["name"] for entry in children}, {*TITLES.values(), "Разрешённый файл"})
        self.assertTrue(all("url" not in entry and entry["id"] not in source.allowed for entry in children))
        file = next(entry for entry in children if entry["name"] == "Разрешённый файл")
        self.assertEqual(file["size_bytes"], 312)
        self.assertEqual(file["modified_at"], "2026-11-22T12:00:00Z")
        source.files["stock"] = "outside-root"
        with self.assertRaisesRegex(ValueError, "outside the demo root"):
            source.load()


class SnapshotTests(TestCase):
    def setUp(self):
        self.reader = drive.Snapshots()
        self.today = date.today()
        self.api = TestClient(main.app)
        snapshots = patch.object(main, "snapshots", self.reader)
        snapshots.start()
        self.addCleanup(snapshots.stop)
        env = patch.dict(drive.os.environ, {"SHOWCASE_GOOGLE_CREDENTIALS_JSON": "", "SHOWCASE_GOOGLE_CREDENTIALS_FILE": ""})
        env.start()
        self.addCleanup(env.stop)

    def source(self):
        return self.api.get("/health").json()["source"]

    def expiry(self):
        register = self.api.get("/api/v1/engineer-documents").json()["data"]["register"]
        self.assertNotIn("source_url", register)
        return register["people"][0]["documents"][0]["entries"][0]["value"]

    def test_cold_refresh_change_schema_and_outage(self):
        tables = seed_tables()
        catalog = [drive.node("Новый разрешённый файл", "proof")]
        self.assertEqual(self.source(), "synthetic")
        with patch.object(drive, "GoogleSource") as source:
            source.return_value.load.return_value = tables, catalog
            self.reader.refresh(self.today)
            before = self.expiry()
            self.assertEqual(self.source(), "drive")
            self.assertEqual(self.api.get("/api/v1/drive-catalog").json()["data"], catalog)

            tables["Документы сотрудников"][1][2] = 45000.0
            tables["Документы сотрудников"][1][7] = 44635
            self.reader.refresh(self.today)
            self.assertNotEqual(self.expiry(), before)
            self.assertEqual(self.expiry(), "2023-03-15")

            tables["Документы сотрудников"][0] = ["Ошибка"]
            self.reader.refresh(self.today)
            self.assertEqual(self.source(), "snapshot")
            self.assertEqual(self.api.get("/health").json()["issue"], "schema")
            self.assertEqual(self.expiry(), "2023-03-15")

            source.return_value.load.side_effect = OSError("network down")
            self.reader.refresh(self.today)
            self.assertEqual(self.source(), "snapshot")
            self.assertEqual(self.api.get("/health").json()["issue"], "unavailable")

            with patch.object(main, "snapshots", drive.Snapshots()):
                self.assertEqual(self.source(), "synthetic")

    def test_cold_call_serves_local_data_during_refresh(self):
        started = Event()
        release = Event()
        finished = Event()

        def load():
            started.set()
            release.wait(5)
            return seed_tables(), drive.local_catalog()

        def refresh(today):
            drive.Snapshots.refresh(self.reader, today)
            finished.set()

        with patch.object(drive, "GoogleSource") as source, patch.dict(
            drive.os.environ, {"SHOWCASE_GOOGLE_CREDENTIALS_JSON": "test"}
        ), patch.object(self.reader, "refresh", side_effect=refresh):
            source.return_value.load.side_effect = load
            try:
                self.assertEqual(self.source(), "synthetic")
                self.assertTrue(started.wait(2))
                self.assertEqual(self.source(), "synthetic")
                self.assertEqual(source.call_count, 1)
            finally:
                release.set()
                self.assertTrue(finished.wait(2))
            self.assertEqual(self.source(), "drive")

    def test_anonymous_read_and_no_client_routes(self):
        for route in ("engineer-documents", "drive-catalog", "dashboard/projects", "dashboard/finance", "dispatch/monthly", "showcase/source", "showcase/settings"):
            self.assertEqual(self.api.get(f"/api/v1/{route}").status_code, 200)
            for method in ("POST", "PUT", "PATCH", "DELETE"):
                self.assertEqual(self.api.request(method, f"/api/v1/{route}").status_code, 405)
        for route in ("files", "auth/me", "integrations/telegram", "platform/companies", "sync/run"):
            self.assertEqual(self.api.get(f"/api/v1/{route}").status_code, 404)

        finance = self.api.get("/api/v1/dashboard/finance?period=quarter").json()["data"]
        projects = self.api.get("/api/v1/dashboard/projects").json()["data"]
        self.assertEqual(finance["total_incoming"], sum(project["paid_sum"] for project in projects))

    def test_formatted_title_and_custom_column_mapping(self):
        tables = seed_tables()
        name = "Документы сотрудников"
        columns = tables[name]
        reordered = [[row[2], row[0], row[1], "поле внешнего учёта"] for row in columns]
        reordered[0][0] = "Срок допуска"
        tables[name] = [["Кадровый реестр"], ["Служебный заголовок"], *reordered]
        data = parse_tables(tables, self.today, {name: {"Действует до": "Срок допуска"}})
        register = data["engineer-documents"]
        self.assertEqual(len(register["people"]), 10)
        self.assertEqual(register["people"][0]["documents"][0]["entries"][0]["value"], columns[1][2])
        self.assertEqual(len(data["customer-tenders"]), 12)
