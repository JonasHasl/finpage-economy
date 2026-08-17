import base64
import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

import pandas as pd
import requests


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from workbook_store import WorkbookConflictError, WorkbookStore


def workbook_bytes(sheets):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for name, dataframe in sheets.items():
            dataframe.to_excel(writer, sheet_name=name, index=False)
    return output.getvalue()


def workbook_data(path, sheet_name):
    return pd.read_excel(path, sheet_name=sheet_name)


class FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class FakeGitHubSession:
    def __init__(self, initial_bytes, *, put_status=200, missing=False):
        self.initial_bytes = initial_bytes
        self.put_status = put_status
        self.missing = missing
        self.get_calls = []
        self.put_calls = []

    def get(self, url, **kwargs):
        self.get_calls.append((url, kwargs))
        if self.missing:
            return FakeResponse(404)
        return FakeResponse(
            200,
            {
                "sha": "current-sha",
                "content": base64.b64encode(self.initial_bytes).decode("ascii"),
            },
        )

    def put(self, url, **kwargs):
        self.put_calls.append((url, kwargs))
        if self.put_status == 409:
            return FakeResponse(409)
        return FakeResponse(200, {"content": {"sha": "new-sha"}})


class WorkbookStoreTests(unittest.TestCase):
    def setUp(self):
        self.initial_sheets = {
            "2015": pd.DataFrame(
                [{"Symbol": "AAA", "ValidFrom": "2026-01-01", "Weight": 0.5}]
            ),
            "2020": pd.DataFrame(
                [{"Symbol": "BBB", "ValidFrom": "2026-01-02", "Weight": 0.5}]
            ),
        }
        self.initial_bytes = workbook_bytes(self.initial_sheets)

    def test_local_replace_sheet_preserves_other_sheets(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workbook_path = Path(temp_dir) / "AlgoComposition.xlsx"
            workbook_path.write_bytes(self.initial_bytes)
            store = WorkbookStore(backend="local", bundled_path=workbook_path)
            replacement = pd.DataFrame(
                [{"Symbol": "CCC", "ValidFrom": "2026-02-01", "Weight": 1.0}]
            )

            store.replace_sheet("2020", replacement)

            self.assertEqual(workbook_data(workbook_path, "2020").iloc[0]["Symbol"], "CCC")
            self.assertEqual(workbook_data(workbook_path, "2015").iloc[0]["Symbol"], "AAA")

    def test_github_replace_uploads_with_the_downloaded_sha(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            session = FakeGitHubSession(self.initial_bytes)
            store = WorkbookStore(
                backend="github",
                bundled_path=Path(temp_dir) / "bundled.xlsx",
                cache_path=Path(temp_dir) / "cache.xlsx",
                repository="owner/finpage-data",
                token="test-token",
                session=session,
            )
            replacement = pd.DataFrame(
                [{"Symbol": "CCC", "ValidFrom": "2026-02-01", "Weight": 1.0}]
            )

            store.replace_sheet("2020", replacement)

            payload = session.put_calls[0][1]["json"]
            self.assertEqual(payload["sha"], "current-sha")
            uploaded = base64.b64decode(payload["content"])
            with tempfile.NamedTemporaryFile(suffix=".xlsx") as uploaded_file:
                uploaded_file.write(uploaded)
                uploaded_file.flush()
                self.assertEqual(
                    workbook_data(uploaded_file.name, "2020").iloc[0]["Symbol"], "CCC"
                )
            self.assertEqual(workbook_data(store.cache_path, "2015").iloc[0]["Symbol"], "AAA")

    def test_github_conflict_does_not_overwrite_the_cached_workbook(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            session = FakeGitHubSession(self.initial_bytes, put_status=409)
            store = WorkbookStore(
                backend="github",
                bundled_path=Path(temp_dir) / "bundled.xlsx",
                cache_path=Path(temp_dir) / "cache.xlsx",
                repository="owner/finpage-data",
                token="test-token",
                session=session,
            )
            replacement = pd.DataFrame(
                [{"Symbol": "CCC", "ValidFrom": "2026-02-01", "Weight": 1.0}]
            )

            with self.assertRaises(WorkbookConflictError):
                store.replace_sheet("2020", replacement)

            self.assertEqual(workbook_data(store.cache_path, "2020").iloc[0]["Symbol"], "BBB")

    def test_github_bootstrap_uploads_the_bundled_backup_when_remote_is_empty(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            bundled_path = Path(temp_dir) / "bundled.xlsx"
            bundled_path.write_bytes(self.initial_bytes)
            session = FakeGitHubSession(self.initial_bytes, missing=True)
            store = WorkbookStore(
                backend="github",
                bundled_path=bundled_path,
                cache_path=Path(temp_dir) / "cache.xlsx",
                repository="owner/finpage-data",
                token="test-token",
                bootstrap_from_local=True,
                session=session,
            )

            self.assertEqual(store.get_path().read_bytes(), self.initial_bytes)
            self.assertNotIn("sha", session.put_calls[0][1]["json"])


if __name__ == "__main__":
    unittest.main()
