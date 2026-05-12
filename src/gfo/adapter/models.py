"""アダプター共通データクラス定義。

全アダプターが返す `_to_*` 変換結果の型をここに集約する。`frozen=True, slots=True`
でイミュータブルかつメモリ効率を確保する。依存は標準ライブラリのみとし、循環参照
防止のため他モジュールを import しない。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PullRequest:
    number: int
    title: str
    body: str | None
    state: str  # "open" | "closed" | "merged"
    author: str
    source_branch: str
    target_branch: str
    draft: bool
    url: str
    created_at: str  # ISO 8601
    updated_at: str | None = None


@dataclass(frozen=True, slots=True)
class Issue:
    number: int
    title: str
    body: str | None
    state: str  # "open" | "closed"
    author: str
    assignees: list[str]
    labels: list[str]
    url: str
    created_at: str
    updated_at: str | None = None


@dataclass(frozen=True, slots=True)
class IssueTemplate:
    name: str
    title: str
    body: str
    about: str
    labels: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Repository:
    name: str
    full_name: str  # "owner/repo"
    description: str | None
    visibility: str  # "public" | "private" | "internal"
    default_branch: str | None
    clone_url: str
    url: str


@dataclass(frozen=True, slots=True)
class Release:
    tag: str
    title: str
    body: str | None
    draft: bool
    prerelease: bool
    url: str
    created_at: str


@dataclass(frozen=True, slots=True)
class Label:
    name: str
    color: str | None
    description: str | None


@dataclass(frozen=True, slots=True)
class Milestone:
    number: int
    title: str
    description: str | None
    state: str  # "open" | "closed"
    due_date: str | None


@dataclass(frozen=True, slots=True)
class Comment:
    id: int
    body: str
    author: str
    url: str
    created_at: str
    updated_at: str | None = None


@dataclass(frozen=True, slots=True)
class Review:
    id: int
    state: str  # "approved" | "changes_requested" | "commented"
    body: str
    author: str
    url: str
    submitted_at: str | None = None


@dataclass(frozen=True, slots=True)
class Branch:
    name: str
    sha: str
    protected: bool
    url: str


@dataclass(frozen=True, slots=True)
class Tag:
    name: str
    sha: str
    message: str
    url: str


@dataclass(frozen=True, slots=True)
class CommitStatus:
    state: str  # "success" | "failure" | "pending" | "error"
    context: str
    description: str
    target_url: str
    created_at: str


@dataclass(frozen=True, slots=True)
class Webhook:
    id: int
    url: str
    events: tuple[str, ...]
    active: bool


@dataclass(frozen=True, slots=True)
class DeployKey:
    id: int
    title: str
    key: str
    read_only: bool


@dataclass(frozen=True, slots=True)
class WikiPage:
    id: int | str  # 数値 ID または sub_url 文字列（Gitea 系）
    title: str
    content: str
    url: str
    updated_at: str | None = None


@dataclass(frozen=True, slots=True)
class Pipeline:
    id: int | str
    status: str  # "success" | "failure" | "running" | "pending" | "cancelled"
    ref: str
    url: str
    created_at: str


@dataclass(frozen=True, slots=True)
class Workflow:
    id: int | str
    name: str
    path: str
    state: str  # "active" | "disabled"


@dataclass(frozen=True, slots=True)
class Artifact:
    id: int | str
    name: str
    size: int
    url: str
    created_at: str


@dataclass(frozen=True, slots=True)
class SshKey:
    id: int | str  # GitHub/GitLab/Gitea 系は int、Bitbucket は UUID 文字列
    title: str
    key: str
    created_at: str


@dataclass(frozen=True, slots=True)
class GpgKey:
    id: int | str
    primary_key_id: str
    public_key: str
    emails: tuple[str, ...]
    created_at: str


@dataclass(frozen=True, slots=True)
class Organization:
    name: str  # ログイン名 / グループパス / ワークスペーススラッグ
    display_name: str  # 表示名（フルネーム）
    description: str | None
    url: str


@dataclass(frozen=True, slots=True)
class Notification:
    id: str
    title: str
    reason: str
    unread: bool
    repository: str
    url: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class Contributor:
    username: str | None
    name: str | None
    email: str | None
    commits: int


@dataclass(frozen=True, slots=True)
class BranchProtection:
    branch: str
    require_reviews: int  # 0 = 無効
    require_status_checks: tuple[str, ...]
    enforce_admins: bool
    allow_force_push: bool
    allow_deletions: bool


@dataclass(frozen=True, slots=True)
class TagProtection:
    id: int | str
    pattern: str
    create_access_level: str


@dataclass(frozen=True, slots=True)
class Secret:
    name: str
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class Variable:
    name: str
    value: str
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class CheckRun:
    name: str
    status: str  # "success" | "failure" | "pending" | "running"
    conclusion: str  # 詳細。不明なら ""
    url: str
    started_at: str


@dataclass(frozen=True, slots=True)
class PullRequestFile:
    filename: str
    status: str  # "added" | "modified" | "deleted" | "renamed"
    additions: int
    deletions: int


@dataclass(frozen=True, slots=True)
class PullRequestCommit:
    sha: str
    message: str
    author: str
    created_at: str


@dataclass(frozen=True, slots=True)
class CompareFile:
    filename: str
    status: str  # "added" | "modified" | "deleted" | "renamed"
    additions: int
    deletions: int


@dataclass(frozen=True, slots=True)
class CompareResult:
    total_commits: int
    ahead_by: int
    behind_by: int
    files: tuple[CompareFile, ...]


@dataclass(frozen=True, slots=True)
class ReleaseAsset:
    id: int | str
    name: str
    size: int
    download_url: str
    created_at: str


@dataclass(frozen=True, slots=True)
class Reaction:
    id: int | str
    content: str  # "+1", "-1", "laugh", "heart", etc.
    user: str
    created_at: str


@dataclass(frozen=True, slots=True)
class TimelineEvent:
    id: int | str
    event: str  # "labeled", "assigned", "closed", etc.
    actor: str
    created_at: str
    detail: str


@dataclass(frozen=True, slots=True)
class Commit:
    sha: str
    message: str
    author: str
    url: str
    created_at: str


@dataclass(frozen=True, slots=True)
class CodeSearchResult:
    path: str  # ファイルパス（リポジトリルートからの相対パス）
    repository: str  # リポジトリ名
    url: str  # Web URL
    matched_text: str  # マッチしたテキスト断片


@dataclass(frozen=True, slots=True)
class Package:
    name: str
    type: str  # "npm", "maven", "container", "pypi", etc.
    version: str
    owner: str
    url: str
    created_at: str


@dataclass(frozen=True, slots=True)
class TimeEntry:
    id: int | str
    user: str
    duration: int  # seconds
    created_at: str


@dataclass(frozen=True, slots=True)
class PushMirror:
    id: int | str
    remote_name: str
    remote_address: str
    interval: str
    created_at: str
    last_update: str | None = None
    last_error: str | None = None


@dataclass(frozen=True, slots=True)
class WikiRevision:
    sha: str
    author: str
    message: str
    created_at: str
