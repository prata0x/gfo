"""gfo label サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse
import re

from gfo.commands import get_adapter
from gfo.exceptions import ConfigError
from gfo.i18n import _
from gfo.output import output


def handle_list(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo label list のハンドラ。"""
    adapter = get_adapter()
    labels = adapter.list_labels()
    output(labels, fmt=fmt, fields=["name", "color", "description"], jq=jq)


def handle_create(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo label create のハンドラ。"""
    name = args.name.strip()
    if not name:
        raise ConfigError(_("name must not be empty."))
    color = args.color
    if color is not None:
        color = color.removeprefix("#")
        if not re.fullmatch(r"[0-9a-fA-F]{6}", color):
            raise ConfigError(
                _("Invalid color '{color}'. Expected 6-digit hex color (e.g. ff0000).").format(
                    color=args.color
                )
            )
    adapter = get_adapter()
    label = adapter.create_label(
        name=name,
        color=color,
        description=args.description,
    )
    output(label, fmt=fmt, jq=jq)


def handle_delete(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo label delete のハンドラ。"""
    name = args.name.strip()
    if not name:
        raise ConfigError(_("name must not be empty."))
    adapter = get_adapter()
    adapter.delete_label(name=name)
    print(_("Deleted label '{name}'.").format(name=name))


def handle_update(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo label update <name> のハンドラ。"""
    name = args.name.strip()
    if not name:
        raise ConfigError(_("name must not be empty."))
    color = args.color
    if color is not None:
        color = color.removeprefix("#")
        if not re.fullmatch(r"[0-9a-fA-F]{6}", color):
            raise ConfigError(
                _("Invalid color '{color}'. Expected 6-digit hex color (e.g. ff0000).").format(
                    color=args.color
                )
            )
    adapter = get_adapter()
    label = adapter.update_label(
        name=name,
        new_name=args.new_name,
        color=color,
        description=args.description,
    )
    output(label, fmt=fmt, jq=jq)


def handle_clone(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo label clone --from owner/repo のハンドラ。"""
    import gfo.adapter.registry
    import gfo.auth
    import gfo.config

    source_repo = getattr(args, "source", None) or getattr(args, "from_repo", None)
    if not source_repo:
        raise ConfigError(_("--from is required."))
    parts = source_repo.split("/", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ConfigError(_("Invalid repo format. Expected 'owner/name'."))
    source_owner, source_name = parts

    config = gfo.config.resolve_project_config()
    token = gfo.auth.resolve_token(config.host, config.service_type)
    api_url = gfo.config.build_default_api_url(
        config.service_type, config.host, config.organization, config.project_key
    )
    client = gfo.adapter.registry.create_http_client(config.service_type, api_url, token)
    adapter_cls = gfo.adapter.registry.get_adapter_class(config.service_type)
    extra_kwargs: dict = {}
    if config.service_type == "backlog" and config.project_key:
        extra_kwargs["project_key"] = config.project_key
    elif config.service_type == "azure-devops":
        if config.organization:
            extra_kwargs["organization"] = config.organization
        if config.project_key:
            extra_kwargs["project_key"] = config.project_key
    source_adapter = adapter_cls(client, source_owner, source_name, **extra_kwargs)

    source_labels = source_adapter.list_labels()
    adapter = get_adapter()
    existing = {lb.name for lb in adapter.list_labels()}
    overwrite = getattr(args, "overwrite", False)
    created = 0
    for lb in source_labels:
        if lb.name in existing and not overwrite:
            continue
        if lb.name in existing and overwrite:
            try:
                adapter.update_label(name=lb.name, color=lb.color, description=lb.description)
            except Exception:  # nosec B110, B112 - best effort overwrite; skip on failure
                continue
        else:
            adapter.create_label(name=lb.name, color=lb.color, description=lb.description)
        created += 1
    print(_("Cloned {count} labels from '{source}'.").format(count=created, source=source_repo))
