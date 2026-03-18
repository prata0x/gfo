"""gfo repo サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse

from gfo.adapter.registry import create_http_client, get_adapter_class
from gfo.auth import resolve_token
from gfo.commands import get_adapter
from gfo.config import (
    build_clone_url,
    build_default_api_url,
    get_default_host,
    get_host_config,
    resolve_project_config,
)
from gfo.detect import detect_service, get_known_service_type, probe_unknown_host
from gfo.exceptions import ConfigError, DetectionError, GitCommandError
from gfo.git_util import git_clone
from gfo.i18n import _
from gfo.output import output


def handle_list(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo repo list のハンドラ。"""
    adapter = get_adapter()
    repos = adapter.list_repositories(
        owner=getattr(args, "owner", None),
        limit=args.limit,
    )
    output(repos, fmt=fmt, fields=["name", "full_name", "private", "description"], jq=jq)


def _resolve_host_without_repo(args_host: str | None) -> tuple[str, str]:
    """リポジトリ外からホストとサービス種別を解決する。

    優先順位:
    1. args_host が指定されている場合はそれを使用
    2. detect_service() でホストを検出
    3. get_default_host() のデフォルトホストを使用
    4. いずれも失敗したら ConfigError
    """
    host: str | None = None

    if args_host:
        host = args_host
    else:
        try:
            result = detect_service()
            host = result.host
        except (DetectionError, GitCommandError):
            host = get_default_host()

    if not host:
        raise ConfigError(
            _("Could not resolve host. Use --host option or set defaults.host in config.toml.")
        )

    # service_type を解決（優先順位: ユーザー設定 > 既知ホスト > ネットワークプローブ）
    host_cfg = get_host_config(host)
    if host_cfg and "type" in host_cfg:
        service_type = host_cfg["type"]
    else:
        service_type = get_known_service_type(host)
        if not service_type:
            service_type = probe_unknown_host(host)
        if not service_type:
            raise ConfigError(
                _(
                    "Could not determine service type for host '{host}'. Configure it in config.toml: [hosts.{host}] type = \"...\""
                ).format(host=host)
            )

    return host, service_type


def handle_create(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo repo create のハンドラ。"""
    host, service_type = _resolve_host_without_repo(getattr(args, "host", None))

    # Azure DevOps と Backlog は API URL 構築・アダプター生成に organization/project_key が必要。
    # 現在のプロジェクト設定から取得を試みる（git リポジトリ外では ConfigError が発生する）。
    organization: str | None = None
    project_key: str | None = None
    if service_type in ("azure-devops", "backlog"):
        try:
            cfg = resolve_project_config()
            if cfg.service_type == service_type:
                organization = cfg.organization
                project_key = cfg.project_key
        except ConfigError:
            pass

    token = resolve_token(host, service_type)
    api_url = build_default_api_url(service_type, host, organization, project_key)

    client = create_http_client(service_type, api_url, token)
    adapter_cls = get_adapter_class(service_type)

    # サービスによってはコンストラクタに追加引数が必要
    extra_kwargs: dict = {}
    if service_type == "backlog":
        if not project_key:
            raise ConfigError(
                _("Backlog requires a project key. Run 'gfo init' first to configure the project.")
            )
        extra_kwargs["project_key"] = project_key
    elif service_type == "azure-devops":
        if not organization or not project_key:
            raise ConfigError(
                _(
                    "Azure DevOps requires an organization and a project. Run 'gfo init' first to configure."
                )
            )
        extra_kwargs["organization"] = organization
        extra_kwargs["project_key"] = project_key

    adapter = adapter_cls(client, "", "", **extra_kwargs)
    repo = adapter.create_repository(
        name=args.name,
        private=getattr(args, "private", False),
        description=getattr(args, "description", "") or "",
    )
    output(repo, fmt=fmt, jq=jq)


def _parse_repo_arg(repo_arg: str) -> tuple[str, str]:
    """'owner/name' 形式の文字列をパースして (owner, name) を返す。"""
    parts = repo_arg.split("/", 1)
    if len(parts) != 2:
        raise ConfigError(
            _(
                "Invalid repo format '{repo_arg}'. Expected 'owner/name' with non-empty owner and name."
            ).format(repo_arg=repo_arg)
        )
    owner, name = parts[0].strip(), parts[1].strip()
    if not owner or not name:
        raise ConfigError(
            _(
                "Invalid repo format '{repo_arg}'. Expected 'owner/name' with non-empty owner and name."
            ).format(repo_arg=repo_arg)
        )
    return owner, name


def handle_clone(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo repo clone のハンドラ。"""
    host, service_type = _resolve_host_without_repo(getattr(args, "host", None))
    owner, name = _parse_repo_arg(args.repo)
    project: str | None = getattr(args, "project", None)
    if service_type == "azure-devops" and project is None:
        try:
            cfg = resolve_project_config()
            if cfg.service_type == "azure-devops":
                project = cfg.project_key
        except ConfigError:
            pass
    url = build_clone_url(service_type, host, owner, name, project=project)
    git_clone(url)


def handle_view(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo repo view のハンドラ。"""
    adapter = get_adapter()

    repo_arg = getattr(args, "repo", None)
    if repo_arg:
        owner, name = _parse_repo_arg(repo_arg)
    else:
        owner, name = None, None

    repo = adapter.get_repository(owner, name)
    output(repo, fmt=fmt, jq=jq)


def handle_delete(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo repo delete のハンドラ。"""
    adapter = get_adapter()
    repo_name = f"{adapter.owner}/{adapter.repo}"
    if not getattr(args, "yes", False):
        confirm = input(
            _(
                "Are you sure you want to delete repository '{repo_name}'? This action cannot be undone. [y/N]: "
            ).format(repo_name=repo_name)
        )
        if confirm.lower() not in ("y", "yes"):
            print(_("Aborted."))
            return
    adapter.delete_repository()
    print(_("Deleted repository '{repo_name}'.").format(repo_name=repo_name))


def handle_fork(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo repo fork のハンドラ。"""
    adapter = get_adapter()
    repo = adapter.fork_repository(organization=getattr(args, "org", None))
    output(repo, fmt=fmt, jq=jq)


def handle_update(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo repo update のハンドラ。"""
    adapter = get_adapter()
    repo = adapter.update_repository(
        description=getattr(args, "description", None),
        private=getattr(args, "private", None),
        default_branch=getattr(args, "default_branch", None),
    )
    output(repo, fmt=fmt, jq=jq)


def handle_archive(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo repo archive のハンドラ。"""
    adapter = get_adapter()
    repo_name = f"{adapter.owner}/{adapter.repo}"
    if not getattr(args, "yes", False):
        confirm = input(
            _("Are you sure you want to archive repository '{repo_name}'? [y/N]: ").format(
                repo_name=repo_name
            )
        )
        if confirm.lower() not in ("y", "yes"):
            print(_("Aborted."))
            return
    adapter.archive_repository()
    print(_("Archived repository '{repo_name}'.").format(repo_name=repo_name))


def handle_languages(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo repo languages のハンドラ。"""
    import json

    from gfo.output import apply_jq_filter

    adapter = get_adapter()
    languages = adapter.get_languages()
    json_str = json.dumps(languages, indent=2, ensure_ascii=False)
    if jq:
        print(apply_jq_filter(json_str, jq))
    else:
        print(json_str)


def handle_topics(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo repo topics のハンドラ。"""
    import json

    from gfo.output import apply_jq_filter

    adapter = get_adapter()
    action = getattr(args, "topics_action", None)
    if action is None:
        raise ConfigError(_("Specify a subcommand: list, add, remove, set"))

    if action == "list":
        topics = adapter.list_topics()
    elif action == "add":
        topics = adapter.add_topic(args.topic)
    elif action == "remove":
        topics = adapter.remove_topic(args.topic)
    elif action == "set":
        topics = adapter.set_topics(args.topics)
    else:
        raise ConfigError(_("Unknown topics action: {action}").format(action=action))

    json_str = json.dumps(topics, indent=2, ensure_ascii=False)
    if jq:
        print(apply_jq_filter(json_str, jq))
    else:
        print(json_str)


def _parse_compare_spec(spec: str) -> tuple[str, str]:
    """compare spec をパースして (base, head) を返す。"""
    for sep in ("...", ".."):
        if sep in spec:
            parts = spec.split(sep, 1)
            return parts[0].strip(), parts[1].strip()
    raise ConfigError(_("Invalid compare spec. Use 'base...head' or 'base..head'."))


def handle_compare(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo repo compare のハンドラ。"""
    adapter = get_adapter()
    base, head = _parse_compare_spec(args.spec)
    result = adapter.compare(base, head)
    output(result, fmt=fmt, jq=jq)


def handle_migrate(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo repo migrate のハンドラ。"""
    adapter = get_adapter()
    repo = adapter.migrate_repository(
        args.clone_url,
        args.name,
        private=getattr(args, "private", False),
        description=getattr(args, "description", "") or "",
        mirror=getattr(args, "mirror", False),
        auth_token=getattr(args, "auth_token", None),
    )
    output(repo, fmt=fmt, jq=jq)


def handle_mirror(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo repo mirror list/add/remove/sync のハンドラ。"""
    adapter = get_adapter()
    action = getattr(args, "mirror_action", None)
    if action is None:
        raise ConfigError(_("Specify a subcommand: list, add, remove, sync"))
    if action == "list":
        mirrors = adapter.list_push_mirrors()
        output(mirrors, fmt=fmt, fields=["id", "remote_name", "remote_address", "interval"], jq=jq)
    elif action == "add":
        mirror = adapter.create_push_mirror(
            args.remote_address,
            interval=getattr(args, "interval", "8h"),
            auth_token=getattr(args, "auth_token", None),
        )
        output(mirror, fmt=fmt, jq=jq)
    elif action == "remove":
        adapter.delete_push_mirror(args.mirror_name)
        print(_("Deleted push mirror '{name}'.").format(name=args.mirror_name))
    elif action == "sync":
        adapter.sync_mirror()
        print(_("Mirror sync triggered."))


def handle_transfer(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo repo transfer <new_owner> のハンドラ。"""
    adapter = get_adapter()
    repo_name = f"{adapter.owner}/{adapter.repo}"
    if not getattr(args, "yes", False):
        confirm = input(
            _(
                "Are you sure you want to transfer repository '{repo_name}' to '{new_owner}'? [y/N]: "
            ).format(repo_name=repo_name, new_owner=args.new_owner)
        )
        if confirm.lower() not in ("y", "yes"):
            print(_("Aborted."))
            return
    team_ids = None
    raw = getattr(args, "team_id", None)
    if raw is not None:
        team_ids = [raw]
    adapter.transfer_repository(args.new_owner, team_ids=team_ids)
    print(
        _("Transferred repository '{repo_name}' to '{new_owner}'.").format(
            repo_name=repo_name, new_owner=args.new_owner
        )
    )


def handle_star(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo repo star のハンドラ。"""
    adapter = get_adapter()
    adapter.star_repository()
    print(_("Starred repository '{owner}/{repo}'.").format(owner=adapter.owner, repo=adapter.repo))


def handle_unstar(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo repo unstar のハンドラ。"""
    adapter = get_adapter()
    adapter.unstar_repository()
    print(
        _("Unstarred repository '{owner}/{repo}'.").format(owner=adapter.owner, repo=adapter.repo)
    )
