"""gfo release サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse

from gfo.commands import get_adapter
from gfo.exceptions import ConfigError
from gfo.i18n import _
from gfo.output import output


def handle_list(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo release list のハンドラ。"""
    adapter = get_adapter()
    releases = adapter.list_releases(limit=args.limit)
    output(releases, fmt=fmt, fields=["tag", "title", "draft", "prerelease"], jq=jq)


def handle_create(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo release create のハンドラ。"""
    tag = (args.tag or "").strip()
    if not tag:
        raise ConfigError(_("tag must not be empty. Use 'gfo release create <tag>'."))
    adapter = get_adapter()
    title = (args.title or "").strip() or tag
    notes = args.notes or ""
    notes_file = getattr(args, "notes_file", None)
    if notes_file:
        notes = notes_file.read()
        notes_file.close()
    release = adapter.create_release(
        tag=tag,
        title=title,
        notes=notes,
        draft=args.draft,
        prerelease=args.prerelease,
        target=getattr(args, "target", None),
    )
    output(release, fmt=fmt, jq=jq)


def handle_delete(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo release delete のハンドラ。"""
    tag = (args.tag or "").strip()
    if not tag:
        raise ConfigError(_("tag must not be empty. Use 'gfo release delete <tag>'."))
    adapter = get_adapter()
    adapter.delete_release(tag=tag)
    print(_("Deleted release '{tag}'.").format(tag=tag))


def handle_view(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo release view のハンドラ。"""
    if getattr(args, "web", False):
        import webbrowser

        adapter = get_adapter()
        if getattr(args, "latest", False):
            release = adapter.get_latest_release()
            webbrowser.open(adapter.get_web_url("release", release.tag))
        else:
            tag = (getattr(args, "tag", None) or "").strip()
            if not tag:
                raise ConfigError(_("tag must not be empty. Specify a tag or use --latest."))
            webbrowser.open(adapter.get_web_url("release", tag))
        return
    adapter = get_adapter()
    if getattr(args, "latest", False):
        release = adapter.get_latest_release()
    else:
        tag = (getattr(args, "tag", None) or "").strip()
        if not tag:
            raise ConfigError(_("tag must not be empty. Specify a tag or use --latest."))
        release = adapter.get_release(tag=tag)
    output(release, fmt=fmt, jq=jq)


def handle_edit(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo release edit のハンドラ。"""
    tag = (args.tag or "").strip()
    if not tag:
        raise ConfigError(_("tag must not be empty."))
    adapter = get_adapter()
    release = adapter.update_release(
        tag=tag,
        title=args.title,
        notes=args.notes,
        draft=args.draft,
        prerelease=args.prerelease,
    )
    output(release, fmt=fmt, jq=jq)


def handle_asset(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo release asset のハンドラ。"""
    action = getattr(args, "asset_action", None)
    if action == "list":
        _handle_asset_list(args, fmt=fmt, jq=jq)
    elif action == "upload":
        _handle_asset_upload(args, fmt=fmt, jq=jq)
    elif action == "download":
        _handle_asset_download(args, fmt=fmt, jq=jq)
    elif action == "delete":
        _handle_asset_delete(args, fmt=fmt, jq=jq)
    else:
        raise ConfigError(_("Specify a subcommand: list, upload, download, delete"))


def _handle_asset_list(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    adapter = get_adapter()
    assets = adapter.list_release_assets(tag=args.tag)
    output(assets, fmt=fmt, fields=["id", "name", "size", "download_url"], jq=jq)


def _handle_asset_upload(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    adapter = get_adapter()
    asset = adapter.upload_release_asset(
        tag=args.tag,
        file_path=args.file,
        name=getattr(args, "name", None),
    )
    output(asset, fmt=fmt, jq=jq)


def _handle_asset_download(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    import fnmatch

    adapter = get_adapter()
    output_dir = getattr(args, "dir", ".") or "."
    asset_id = getattr(args, "asset_id", None)
    pattern = getattr(args, "pattern", None)

    if asset_id:
        path = adapter.download_release_asset(
            tag=args.tag,
            asset_id=asset_id,
            output_dir=output_dir,
        )
        print(_("Downloaded: {path}").format(path=path))
    elif pattern:
        assets = adapter.list_release_assets(tag=args.tag)
        matched = [a for a in assets if fnmatch.fnmatch(a.name, pattern)]
        if not matched:
            raise ConfigError(_("No assets match pattern '{pattern}'.").format(pattern=pattern))
        for a in matched:
            path = adapter.download_release_asset(
                tag=args.tag,
                asset_id=a.id,
                output_dir=output_dir,
            )
            print(_("Downloaded: {path}").format(path=path))
    else:
        raise ConfigError(_("Specify --asset-id or --pattern."))


def _handle_asset_delete(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    adapter = get_adapter()
    adapter.delete_release_asset(tag=args.tag, asset_id=args.asset_id)
    print(_("Deleted asset '{asset_id}'.").format(asset_id=args.asset_id))
