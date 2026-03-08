"""GitBucket アダプター。GitHubAdapter を継承し、service_name のみオーバーライドする。"""

from __future__ import annotations

from .github import GitHubAdapter
from .registry import register


@register("gitbucket")
class GitBucketAdapter(GitHubAdapter):
    service_name = "GitBucket"
