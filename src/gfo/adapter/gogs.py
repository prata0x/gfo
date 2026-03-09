"""Gogs アダプター。GiteaAdapter を継承し、PR / Label / Milestone 操作を NotSupportedError でオーバーライドする。"""

from __future__ import annotations

import urllib.parse

from gfo.exceptions import NotSupportedError

from .gitea import GiteaAdapter
from .registry import register


@register("gogs")
class GogsAdapter(GiteaAdapter):
    """Gitea を継承。PR / Label / Milestone 操作を NotSupportedError でオーバーライド。"""

    service_name = "Gogs"

    def _web_url(self) -> str:
        """Web UI のベース URL を構築する。"""
        parsed = urllib.parse.urlparse(self._client.base_url)
        return f"{parsed.scheme}://{parsed.hostname}" + (f":{parsed.port}" if parsed.port else "")

    # --- PR（非サポート）---

    def list_pull_requests(self, *, state="open", limit=30):
        raise NotSupportedError("Gogs", "pull request operations",
                                web_url=f"{self._web_url()}/{self._owner}/{self._repo}/pulls")

    def create_pull_request(self, *, title, body="", base, head, draft=False):
        raise NotSupportedError("Gogs", "pull request operations",
                                web_url=f"{self._web_url()}/{self._owner}/{self._repo}/compare")

    def get_pull_request(self, number):
        raise NotSupportedError("Gogs", "pull request operations",
                                web_url=f"{self._web_url()}/{self._owner}/{self._repo}/pulls/{number}")

    def merge_pull_request(self, number, *, method="merge"):
        raise NotSupportedError("Gogs", "pull request operations",
                                web_url=f"{self._web_url()}/{self._owner}/{self._repo}/pulls/{number}")

    def close_pull_request(self, number):
        raise NotSupportedError("Gogs", "pull request operations",
                                web_url=f"{self._web_url()}/{self._owner}/{self._repo}/pulls/{number}")

    def get_pr_checkout_refspec(self, number, *, pr=None):
        raise NotSupportedError("Gogs", "pull request operations",
                                web_url=f"{self._web_url()}/{self._owner}/{self._repo}/pulls/{number}")

    # --- Label（非サポート）---

    def list_labels(self):
        raise NotSupportedError("Gogs", "label operations")

    def create_label(self, *, name, color=None, description=None):
        raise NotSupportedError("Gogs", "label operations")

    # --- Milestone（非サポート）---

    def list_milestones(self):
        raise NotSupportedError("Gogs", "milestone operations")

    def create_milestone(self, *, title, description=None, due_date=None):
        raise NotSupportedError("Gogs", "milestone operations")
