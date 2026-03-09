"""GitBucket アダプター。GitHubAdapter を継承し、service_name のみオーバーライドする。

GitBucket は GitHub API v3 互換の自己ホスト型 Git サーバー。
API パスや認証方式はほぼ同一のため GitHubAdapter を再利用する。
GitBucket 固有の非互換（ラベル color フォーマット差異等）が判明した場合は
このクラスでオーバーライドして対応する。
"""

from __future__ import annotations

from .github import GitHubAdapter
from .registry import register


@register("gitbucket")
class GitBucketAdapter(GitHubAdapter):
    service_name = "GitBucket"
