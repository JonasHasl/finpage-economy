"""Safe local and GitHub-backed storage for ``AlgoComposition.xlsx``."""

from __future__ import annotations

import base64
import os
import tempfile
import threading
from io import BytesIO
from pathlib import Path
from typing import Mapping
from urllib.parse import quote

import pandas as pd
import requests


class WorkbookStoreError(RuntimeError):
    """Raised when the algorithm workbook cannot be loaded or saved safely."""


class WorkbookConflictError(WorkbookStoreError):
    """Raised when the GitHub copy changed while a user was editing it."""


class WorkbookStore:
    """Keep the workbook local by default and use GitHub only when configured."""

    def __init__(
        self,
        *,
        backend: str,
        bundled_path: Path,
        cache_path: Path | None = None,
        repository: str | None = None,
        branch: str = "main",
        remote_path: str = "AlgoComposition.xlsx",
        token: str | None = None,
        bootstrap_from_local: bool = False,
        session: requests.Session | None = None,
    ):
        self.backend = backend.lower()
        self.bundled_path = Path(bundled_path)
        self.cache_path = Path(cache_path) if cache_path else self.bundled_path
        self.repository = repository
        self.branch = branch
        self.remote_path = remote_path
        self.token = token
        self.bootstrap_from_local = bootstrap_from_local
        self.session = session or requests.Session()
        self._lock = threading.RLock()
        self._remote_sha: str | None = None

        if self.backend not in {"local", "github"}:
            raise WorkbookStoreError(
                "ALGO_WORKBOOK_BACKEND must be either 'local' or 'github'."
            )

    @classmethod
    def from_environment(cls, environment: Mapping[str, str] | None = None):
        environment = environment or os.environ
        bundled_path = Path(
            environment.get(
                "ALGO_WORKBOOK_LOCAL_PATH",
                str(Path(__file__).resolve().parent / "AlgoComposition.xlsx"),
            )
        )
        backend = environment.get("ALGO_WORKBOOK_BACKEND", "local")
        cache_path = Path(
            environment.get(
                "ALGO_WORKBOOK_CACHE_PATH",
                str(Path(tempfile.gettempdir()) / "finpage" / "AlgoComposition.xlsx"),
            )
        )

        return cls(
            backend=backend,
            bundled_path=bundled_path,
            cache_path=cache_path if backend.lower() == "github" else bundled_path,
            repository=environment.get("GITHUB_WORKBOOK_REPOSITORY"),
            branch=environment.get("GITHUB_WORKBOOK_BRANCH", "main"),
            remote_path=environment.get("GITHUB_WORKBOOK_PATH", "AlgoComposition.xlsx"),
            token=environment.get("GITHUB_WORKBOOK_TOKEN"),
            bootstrap_from_local=_as_bool(
                environment.get("GITHUB_WORKBOOK_BOOTSTRAP_FROM_LOCAL", "false")
            ),
        )

    @property
    def uses_github(self) -> bool:
        return self.backend == "github"

    def get_path(self) -> Path:
        """Return a current readable workbook path, downloading it on first use."""
        with self._lock:
            if self.uses_github and not self.cache_path.exists():
                self._download_or_bootstrap()

            path = self.cache_path if self.uses_github else self.bundled_path
            if not path.exists():
                raise WorkbookStoreError(
                    f"Algorithm workbook was not found at {path}."
                )
            return path

    def replace_sheet(self, sheet_name: str, reviewed_df: pd.DataFrame) -> None:
        """Replace one sheet without changing the durable copy until it is safe."""
        with self._lock:
            if self.uses_github:
                self._download_or_bootstrap()

            path = self.get_path()
            workbook = pd.read_excel(path, sheet_name=None)
            if sheet_name not in workbook:
                raise WorkbookStoreError(
                    f"Workbook does not contain a '{sheet_name}' sheet."
                )

            updated_bytes = _workbook_with_replaced_sheet(
                workbook, sheet_name, reviewed_df
            )

            if self.uses_github:
                self._upload(updated_bytes, expected_sha=self._remote_sha)

            self._atomic_write(self.cache_path if self.uses_github else self.bundled_path, updated_bytes)

    def _download_or_bootstrap(self) -> None:
        self._require_github_configuration()
        response = self.session.get(
            self._contents_url,
            headers=self._headers(),
            params={"ref": self.branch},
            timeout=20,
        )

        if response.status_code == 404:
            if not self.bootstrap_from_local:
                raise WorkbookStoreError(
                    "The configured GitHub repository does not yet contain the "
                    "workbook. Add it first, or temporarily set "
                    "GITHUB_WORKBOOK_BOOTSTRAP_FROM_LOCAL=true."
                )
            if not self.bundled_path.exists():
                raise WorkbookStoreError(
                    "Cannot bootstrap GitHub because the bundled workbook is missing."
                )
            initial_bytes = self.bundled_path.read_bytes()
            self._upload(initial_bytes, expected_sha=None)
            self._atomic_write(self.cache_path, initial_bytes)
            return

        try:
            response.raise_for_status()
            payload = response.json()
            content = payload["content"].replace("\n", "")
            workbook_bytes = base64.b64decode(content)
            remote_sha = payload["sha"]
        except (KeyError, ValueError, requests.RequestException) as exc:
            raise WorkbookStoreError(
                "Could not download the algorithm workbook from GitHub."
            ) from exc

        self._atomic_write(self.cache_path, workbook_bytes)
        self._remote_sha = remote_sha

    def _upload(self, workbook_bytes: bytes, expected_sha: str | None) -> None:
        self._require_github_configuration()
        payload = {
            "message": "Update AlgoComposition.xlsx from algo-helper",
            "content": base64.b64encode(workbook_bytes).decode("ascii"),
            "branch": self.branch,
        }
        if expected_sha:
            payload["sha"] = expected_sha

        response = self.session.put(
            self._contents_url,
            headers=self._headers(),
            json=payload,
            timeout=20,
        )
        if response.status_code == 409:
            raise WorkbookConflictError(
                "The GitHub workbook changed while this table was being edited. "
                "Reload the page, review the latest data, and try again."
            )

        try:
            response.raise_for_status()
            self._remote_sha = response.json()["content"]["sha"]
        except (KeyError, ValueError, requests.RequestException) as exc:
            raise WorkbookStoreError(
                "Could not save the algorithm workbook to GitHub; the existing "
                "workbook was left unchanged."
            ) from exc

    @property
    def _contents_url(self) -> str:
        if not self.repository:
            return ""
        return (
            f"https://api.github.com/repos/{self.repository}/contents/"
            f"{quote(self.remote_path, safe='/')}"
        )

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _require_github_configuration(self) -> None:
        if not self.repository or "/" not in self.repository or not self.token:
            raise WorkbookStoreError(
                "GitHub workbook sync requires GITHUB_WORKBOOK_REPOSITORY "
                "(owner/repository) and GITHUB_WORKBOOK_TOKEN."
            )

    @staticmethod
    def _atomic_write(path: Path, workbook_bytes: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            dir=path.parent, prefix=".AlgoComposition-", suffix=".tmp", delete=False
        ) as temp_file:
            temp_file.write(workbook_bytes)
            temp_path = Path(temp_file.name)
        temp_path.replace(path)


def _as_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _workbook_with_replaced_sheet(
    workbook: dict[str, pd.DataFrame], sheet_name: str, reviewed_df: pd.DataFrame
) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for existing_sheet, existing_df in workbook.items():
            dataframe = reviewed_df if existing_sheet == sheet_name else existing_df
            dataframe.to_excel(writer, sheet_name=existing_sheet, index=False)
    return output.getvalue()


workbook_store = WorkbookStore.from_environment()


def get_workbook_path() -> Path:
    return workbook_store.get_path()


def replace_workbook_sheet(sheet_name: str, reviewed_df: pd.DataFrame) -> None:
    workbook_store.replace_sheet(sheet_name, reviewed_df)
