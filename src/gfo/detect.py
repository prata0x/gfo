"""git remote URL からサービス種別・ホスト名・owner/repo を検出するモジュール。"""

from __future__ import annotations

import dataclasses
import re
import sys
from dataclasses import dataclass

from gfo.exceptions import DetectionError


def _mask_credentials(text: str) -> str:
    """URL 内の認証情報（`://user:pass@` 形式）をマスクする。"""
    return re.sub(r"://[^@\s]+@", "://***@", text)
from gfo.git_util import get_remote_url, git_config_get


# ── データクラス ──


@dataclass(frozen=True)
class DetectResult:
    """検出結果。イミュータブル。フィールドの変更には dataclasses.replace() を使用する。"""

    service_type: str | None  # "github", "gitlab", "bitbucket", "azure-devops",
    #                           "gitea", "forgejo", "gogs", "gitbucket", "backlog"
    host: str
    owner: str
    repo: str
    api_url: str | None = None
    organization: str | None = None  # Azure DevOps 用
    project: str | None = None  # Azure DevOps / Backlog 用


# ── URL パース正規表現 ──

_HTTPS_RE = re.compile(
    r"^https?://(?P<host>[^/:]+)(?::(?P<port>\d+))?/(?P<path>.+?)(?:\.git)?/?$"
)

_SSH_URL_RE = re.compile(
    r"^ssh://(?:[^\s@]+@)?(?P<host>[^/:]+)(?::(?P<port>\d+))?/(?P<path>.+?)(?:\.git)?/?$"
)

_SSH_SCP_RE = re.compile(
    r"^(?:[^\s@]+@)?(?P<host>[^:]+):(?P<path>.+?)(?:\.git)?/?$"
)


# ── パスパーサー正規表現 ──

# Azure DevOps: {org}/{project}/_git/{repo} or v3/{org}/{project}/{repo}
_AZURE_GIT_PATH_RE = re.compile(
    r"^(?:(?P<org>[^/]+)/)?(?P<project>[^/]+)/_git/(?P<repo>[^/]+)$"
)
_AZURE_V3_PATH_RE = re.compile(
    r"^v3/(?P<org>[^/]+)/(?P<project>[^/]+)/(?P<repo>[^/]+)$"
)

_BACKLOG_PATH_RE = re.compile(
    r"^git/(?P<project>[^/]+)/(?P<repo>[^/]+)$"
)

_GITBUCKET_PATH_RE = re.compile(
    r"^git/(?P<owner>[^/]+)/(?P<repo>[^/]+)$"
)

_GENERIC_PATH_RE = re.compile(
    r"^(?P<owner>.+)/(?P<repo>[^/]+)$"
)


# ── 既知ホストテーブル ──

_KNOWN_HOSTS: dict[str, str] = {
    "github.com": "github",
    "gitlab.com": "gitlab",
    "bitbucket.org": "bitbucket",
    "dev.azure.com": "azure-devops",
    "ssh.dev.azure.com": "azure-devops",
    "codeberg.org": "forgejo",
}


# ── URL パース ──


def _parse_url(remote_url: str) -> tuple[str, str]:
    """remote URL から (host, path) を抽出する。"""
    for pattern in (_HTTPS_RE, _SSH_URL_RE, _SSH_SCP_RE):
        m = pattern.match(remote_url)
        if m:
            return m.group("host"), m.group("path")
    raise DetectionError(f"Cannot parse URL: {_mask_credentials(remote_url)}")


def detect_from_url(remote_url: str) -> DetectResult:
    """remote URL をパースし、ホスト・owner・repo を抽出する。"""
    host, path = _parse_url(remote_url)

    # Backlog SSH 特殊処理: *.git.backlog.{com,jp} → *.backlog.{com,jp}
    is_backlog = False
    for suffix in (".backlog.com", ".backlog.jp"):
        git_suffix = ".git" + suffix
        if host.endswith(git_suffix):
            host = host.replace(".git" + suffix, suffix)
            path = path.lstrip("/")
            is_backlog = True
            break

    # Backlog サフィックスマッチ (HTTPS)
    if not is_backlog:
        for suffix in (".backlog.com", ".backlog.jp"):
            if host.endswith(suffix):
                is_backlog = True
                break

    if is_backlog:
        # Backlog HTTPS: path = "git/{PROJECT}/{repo}"
        m = _BACKLOG_PATH_RE.match(path)
        if m:
            return DetectResult(
                service_type="backlog",
                host=host,
                owner=m.group("project"),
                repo=m.group("repo"),
                project=m.group("project"),
            )
        # Backlog SSH: path = "{PROJECT}/{repo}" (lstrip 済み)
        m = _GENERIC_PATH_RE.match(path)
        if m:
            return DetectResult(
                service_type="backlog",
                host=host,
                owner=m.group("owner"),
                repo=m.group("repo"),
                project=m.group("owner"),
            )
        raise DetectionError(f"Cannot parse Backlog path: {_mask_credentials(path)}")

    # 既知ホストテーブル照合
    service_type = _KNOWN_HOSTS.get(host)

    # *.visualstudio.com → azure-devops
    if service_type is None and host.endswith(".visualstudio.com"):
        service_type = "azure-devops"

    # Azure DevOps パス処理
    if service_type == "azure-devops":
        m = _AZURE_GIT_PATH_RE.match(path) or _AZURE_V3_PATH_RE.match(path)
        if m:
            org = m.group("org") or ""
            # legacy *.visualstudio.com: org はホストのサブドメイン部分
            if host.endswith(".visualstudio.com") or not org:
                org = host.split(".")[0]
            return DetectResult(
                service_type="azure-devops",
                host=host,
                owner=org,
                repo=m.group("repo"),
                organization=org,
                project=m.group("project"),
            )
        raise DetectionError(f"Cannot parse Azure DevOps path: {_mask_credentials(path)}")

    # 既知ホスト + 汎用パス
    if service_type is not None:
        m = _GENERIC_PATH_RE.match(path)
        if m:
            return DetectResult(
                service_type=service_type,
                host=host,
                owner=m.group("owner"),
                repo=m.group("repo"),
            )
        raise DetectionError(f"Cannot parse path: {_mask_credentials(path)}")

    # 未知ホスト → service_type=None
    m = _GENERIC_PATH_RE.match(path)
    if m:
        return DetectResult(
            service_type=None,
            host=host,
            owner=m.group("owner"),
            repo=m.group("repo"),
        )
    raise DetectionError(f"Cannot parse path: {path}")


# ── API プローブ ──


def probe_unknown_host(host: str, scheme: str = "https") -> str | None:
    """未知ホストに対して API プローブを実行し、サービス種別を返す。"""
    import requests

    base = f"{scheme}://{host}"

    # 1. Gitea/Forgejo/Gogs (v1)
    # /api/v1/version のレスポンス仕様:
    #   Gogs    {"version": "0.x.x"}
    #   Gitea   {"version": "1.x.x", "go_version": "go1.x", ...}
    #   Forgejo {"version": "...", "forgejo": "...", "go_version": "..."}  (>= 1.20)
    #           {"version": "...", "go_version": "...", "source_url": "https://codeberg.org/forgejo/forgejo"}  (旧版)
    try:
        resp = requests.get(f"{base}/api/v1/version", timeout=5, verify=True)
        if resp.status_code == 200:
            data = resp.json()
            # Forgejo >= 1.20 は "forgejo" キーを持つ
            if "forgejo" in data:
                return "forgejo"
            # 旧版 Forgejo は source_url に "forgejo" を含む場合がある
            source_url = data.get("source_url", "")
            if isinstance(source_url, str) and "forgejo" in source_url.lower():
                return "forgejo"
            # Gitea は go_version / go-version キーを持つ（Gogs は持たない）
            if "go-version" in data or "go_version" in data:
                return "gitea"
            # Gogs は version のみ持ち、go_version/forgejo を持たない
            if "version" in data and "go-version" not in data and "go_version" not in data and "forgejo" not in data:
                return "gogs"
    except (requests.ConnectionError, requests.Timeout, requests.RequestException):
        pass

    # 2. GitLab (v4)
    try:
        resp = requests.get(f"{base}/api/v4/version", timeout=5, verify=True)
        if resp.status_code == 200:
            return "gitlab"
    except (requests.ConnectionError, requests.Timeout, requests.RequestException):
        pass

    # 3. GitBucket (v3)
    try:
        resp = requests.get(f"{base}/api/v3/", timeout=5, verify=True)
        if resp.status_code == 200:
            return "gitbucket"
    except (requests.ConnectionError, requests.Timeout, requests.RequestException):
        pass

    return None


# ── 統合検出フロー ──


def detect_service(cwd: str | None = None) -> DetectResult:
    """完全な検出フローを実行する。"""
    # 1. git config ショートカット
    stype = git_config_get("gfo.type", cwd=cwd)
    shost = git_config_get("gfo.host", cwd=cwd)
    if stype and shost:
        remote_url = get_remote_url(cwd=cwd)
        result = detect_from_url(remote_url)
        # URL パース結果と git config 設定が食い違う場合に警告
        if result.service_type is not None and result.service_type != stype:
            print(
                f"warning: gfo.type={stype!r} but URL suggests {result.service_type!r}; "
                "using git config value.",
                file=sys.stderr,
            )
        # service_type と host を git config の値で統一する
        result = dataclasses.replace(result, service_type=stype, host=shost)
        return result

    # 2. URL パース
    remote_url = get_remote_url(cwd=cwd)
    result = detect_from_url(remote_url)

    # 3. config.toml hosts 参照
    if result.service_type is None:
        try:
            # 循環依存回避のため遅延インポートを使用。
            # detect.py はモジュールレベルで config.py を import できない:
            #   config.py → resolve_project_config() で gfo.detect を遅延 import
            #   detect.py → detect_service() で gfo.config を遅延 import
            # 両者が互いを参照するため、トップレベル import にすると循環 ImportError が発生する。
            import gfo.config

            hosts = gfo.config.get_hosts_config()
            service_from_hosts = hosts.get(result.host)
            if service_from_hosts is not None:
                result = dataclasses.replace(result, service_type=service_from_hosts)
        except (ImportError, AttributeError):
            pass

    # 4. プローブ（SSH URL も含め常に HTTPS を優先する）
    if result.service_type is None:
        scheme = "http" if remote_url.startswith("http://") else "https"
        probed = probe_unknown_host(result.host, scheme=scheme)
        if probed is not None:
            result = dataclasses.replace(result, service_type=probed)

    # 5. 全失敗
    if result.service_type is None:
        raise DetectionError(f"Unknown host: {result.host}")

    return result
