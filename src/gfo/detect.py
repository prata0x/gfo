"""git remote URL からサービス種別・ホスト名・owner/repo を検出するモジュール。"""

from __future__ import annotations

import dataclasses
import os
import re
import warnings
from dataclasses import dataclass
from urllib.parse import urlparse

import requests

from gfo.exceptions import DetectionError, GitCommandError
from gfo.git_util import _mask_credentials, get_remote_url, git_config_get


def normalize_host(value: str) -> str:
    """ホスト文字列を正規化する。URL が渡された場合はホスト名:ポート部分を抽出する。"""
    if "://" in value:
        parsed = urlparse(value)
        hostname = parsed.hostname or value
        if parsed.port:
            return f"{hostname.lower()}:{parsed.port}"
        return hostname.lower()
    return value.strip().rstrip("/").lower()


# GFO_INSECURE は self-hosted のみ有効化対象。クラウド固定ホストでは無視する。
# クラウドホスト判定は gfo.http に集約してあるため、ホストごとに動的解決する。
from gfo.http import _is_cloud_host_tls_forced as _http_cloud_check  # noqa: E402


def _verify_for_host(host: str) -> bool:
    """指定ホストに対する verify フラグを返す。クラウド固定ホストは常に True。"""
    if _http_cloud_check(host):
        return True
    return os.environ.get("GFO_INSECURE", "").lower() not in ("1", "true", "yes")


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
    r"^https?://(?:[^\s@]+@)?(?P<host>[^/:]+)(?::(?P<port>\d+))?/(?P<path>.+?)(?:\.git)?/?$"
)

_SSH_URL_RE = re.compile(
    r"^ssh://(?:[^\s@]+@)?(?P<host>[^/:]+)(?::(?P<port>\d+))?/(?P<path>.+?)(?:\.git)?/?$"
)

_SSH_SCP_RE = re.compile(r"^(?:[^\s@]+@)?(?P<host>[^:]+):(?P<path>.+?)(?:\.git)?/?$")


# ── パスパーサー正規表現 ──

# Azure DevOps: {org}/{project}/_git/{repo} or v3/{org}/{project}/{repo}
_AZURE_GIT_PATH_RE = re.compile(r"^(?:(?P<org>[^/]+)/)?(?P<project>[^/]+)/_git/(?P<repo>[^/]+)$")
_AZURE_V3_PATH_RE = re.compile(r"^v3/(?P<org>[^/]+)/(?P<project>[^/]+)/(?P<repo>[^/]+)$")

# Backlog HTTPS の URL パス（`git/{owner}/{repo}`）用パターン。
_GIT_PATH_RE = re.compile(r"^git/(?P<owner>[^/]+)/(?P<repo>[^/]+)$")
_BACKLOG_PATH_RE = _GIT_PATH_RE

_GENERIC_PATH_RE = re.compile(r"^(?P<owner>.+)/(?P<repo>[^/]+)$")


# ── 既知ホストテーブル ──

_KNOWN_HOSTS: dict[str, str] = {
    "github.com": "github",
    "gitlab.com": "gitlab",
    "bitbucket.org": "bitbucket",
    "dev.azure.com": "azure-devops",
    "ssh.dev.azure.com": "azure-devops",
    "codeberg.org": "forgejo",
}


def get_known_service_type(host: str) -> str | None:
    """既知ホストテーブルからサービス種別を返す。未知ホストの場合は None。"""
    return _KNOWN_HOSTS.get(host.lower())


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
            project_key = m.group("owner")  # グループ名は owner に統一済み
            return DetectResult(
                service_type="backlog",
                host=host,
                owner=project_key,
                repo=m.group("repo"),
                project=project_key,
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
    service_type = _KNOWN_HOSTS.get(host.lower())

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
    raise DetectionError(f"Cannot parse path: {_mask_credentials(path)}")


# ── API プローブ ──


def _is_private_host(host: str) -> bool:
    """ホスト名/IP がプライベートレンジ・ループバック・リンクローカルかを判定する。

    ホスト名の場合は socket.gethostbyname で IP 解決し、ipaddress で判定する。
    DNS 解決失敗時は安全側に倒して True を返す (プローブを拒否)。これは
    存在しないホスト名で SSRF プローブを誘発する攻撃面を狭めるための判断。
    """
    import ipaddress
    import socket

    if not host:
        return False
    # ホスト名から : ポート分離
    h = host.split(":", 1)[0]
    try:
        ip_str = socket.gethostbyname(h)
        ip = ipaddress.ip_address(ip_str)
    except (OSError, ValueError):
        # DNS 失敗・無効 IP は「不明」だがプローブは拒否側 (True) に倒す。
        return True
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved


def probe_unknown_host(host: str, scheme: str = "https") -> str | None:
    """未知ホストに対して API プローブを実行し、サービス種別を返す。

    SSRF プローブを防ぐため、プライベート IP / ループバック / リンクローカル /
    予約レンジへのプローブは既定で拒否する（None を返す）。
    GFO_ALLOW_PRIVATE_HOSTS=1 を設定すると opt-in で許可する。
    """
    if _is_private_host(host) and os.environ.get("GFO_ALLOW_PRIVATE_HOSTS", "").lower() not in (
        "1",
        "true",
        "yes",
    ):
        return None
    base = f"{scheme}://{host}"

    # 1. Gitea/Forgejo/Gogs (v1)
    # /api/v1/version のレスポンス仕様:
    #   Gogs    {"version": "0.x.x"}
    #   Gitea   {"version": "1.x.x", "go_version": "go1.x", ...}
    #   Forgejo {"version": "...", "forgejo": "...", "go_version": "..."}  (>= 1.20)
    #           {"version": "...", "go_version": "...", "source_url": "..."}  (旧版 Forgejo)
    try:
        resp = requests.get(
            f"{base}/api/v1/version",
            timeout=5,
            verify=_verify_for_host(host),
            allow_redirects=False,
        )
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict):
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
                # version のみでキー判別できない場合、バージョン番号で区別
                # Gogs: 0.x.x / Gitea・Forgejo: 1.x.x 以上
                if (
                    "version" in data
                    and "go-version" not in data
                    and "go_version" not in data
                    and "forgejo" not in data
                ):
                    ver = data.get("version", "")
                    if isinstance(ver, str) and ver.startswith("0."):
                        return "gogs"
                    return "gitea"
    except (requests.RequestException, ValueError):
        # ValueError: resp.json() が非 JSON レスポンスを受け取った場合
        pass

    # 2. GitLab (v4)
    try:
        resp = requests.get(
            f"{base}/api/v4/version",
            timeout=5,
            verify=_verify_for_host(host),
            allow_redirects=False,
        )
        if resp.status_code == 200:
            return "gitlab"
    except requests.RequestException:
        pass

    # 3. GitBucket (v3)
    try:
        resp = requests.get(
            f"{base}/api/v3/", timeout=5, verify=_verify_for_host(host), allow_redirects=False
        )
        if resp.status_code == 200:
            return "gitbucket"
    except requests.RequestException:
        pass

    return None


# ── --repo オプションパーサー ──


def _parse_repo_option(value: str) -> DetectResult:
    """--repo オプションの値をパースして DetectResult を返す。"""
    from gfo.exceptions import ConfigError
    from gfo.i18n import _

    if not value or not value.strip():
        raise ConfigError(_("--repo value must not be empty. Use URL or HOST/OWNER/REPO format."))

    # 1. URL 形式を試す (https://, ssh://, git@host:path)
    try:
        return detect_from_url(value)
    except DetectionError:
        pass

    # 2. HOST/PATH 形式 → https:// を補完して再試行
    # ただし、HOST/OWNER/REPO の 3 セグメント以上 (slash >= 2) を要求して
    # 単一ホスト名や short string が誤って HTTPS プローブされるのを防ぐ。
    if value.count("/") < 2:
        raise ConfigError(
            _("Cannot parse --repo value: {value}. Use URL or HOST/OWNER/REPO format.").format(
                value=value
            )
        )
    try:
        return detect_from_url(f"https://{value}")
    except DetectionError as e:
        raise ConfigError(
            _("Cannot parse --repo value: {value}. Use URL or HOST/OWNER/REPO format.").format(
                value=value
            )
        ) from e


# ── 統合検出フロー ──


def detect_service(cwd: str | None = None) -> DetectResult:
    """完全な検出フローを実行する。"""
    from gfo._context import cli_remote, cli_repo

    override_repo = cli_repo.get()
    override_remote = cli_remote.get()

    # --repo 指定時: URL/HOST/PATH からパースし、サービス検出フローに合流
    if override_repo:
        result = _parse_repo_option(override_repo)
    elif not override_remote:
        # --remote も --repo も未指定時
        # 1. git config ショートカット（saved_type / saved_host: git config に保存済みの値）
        saved_type = git_config_get("gfo.type", cwd=cwd)
        saved_host = git_config_get("gfo.host", cwd=cwd)
        if saved_type and saved_host:
            try:
                remote_url = get_remote_url(cwd=cwd)
            except GitCommandError:
                # remote が存在しない（bare repo / CI で `git init` 直後 / リモート未設定）
                # 場合でも、`gfo init` で保存済みの saved_type/host だけで auth 系コマンドが
                # 動くようにフォールバックする。owner/repo は空文字で返す（auth login/token/
                # status 等は host のみあれば成立し、owner/repo を要求するコマンドは別途
                # ConfigError になる）。
                return DetectResult(service_type=saved_type, host=saved_host, owner="", repo="")
            result = detect_from_url(remote_url)
            # URL パース結果と git config 設定が食い違う場合に警告
            if result.service_type is not None and result.service_type != saved_type:
                warnings.warn(
                    f"gfo.type={saved_type!r} but URL suggests {result.service_type!r}; "
                    "using git config value.",
                    stacklevel=2,
                )
            # service_type と host を git config の値で統一する
            result = dataclasses.replace(result, service_type=saved_type, host=saved_host)
            return result
        # git config ショートカット不成立 → URL パースへ
        remote_url = get_remote_url(cwd=cwd)
        result = detect_from_url(remote_url)
    else:
        # 2. --remote 指定時: URL パース
        remote_url = get_remote_url(remote=override_remote, cwd=cwd)
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
            service_from_hosts = hosts.get(result.host.lower())
            if service_from_hosts is not None:
                result = dataclasses.replace(result, service_type=service_from_hosts)
        except (ImportError, AttributeError):
            pass

    # 4. プローブ（SSH URL も含め常に HTTPS を優先する）
    if result.service_type is None:
        # --repo 指定時は remote_url が存在しないため常に https
        if override_repo:
            scheme = "https"
        else:
            scheme = "http" if remote_url.startswith("http://") else "https"
        probed = probe_unknown_host(result.host, scheme=scheme)
        if probed is not None:
            result = dataclasses.replace(result, service_type=probed)

    # 5. 全失敗
    if result.service_type is None:
        raise DetectionError(f"Unknown host: {result.host}")

    return result
