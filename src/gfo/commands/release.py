"""gfo release サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse

from gfo.commands import get_adapter, open_in_browser, read_file_arg
from gfo.exceptions import ConfigError, GfoError
from gfo.i18n import _
from gfo.output import output


def handle_list(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo release list のハンドラ。"""
    if getattr(args, "web", False):
        open_in_browser(get_adapter(), "release")
        return
    adapter = get_adapter()
    draft = getattr(args, "draft", None)
    prerelease = getattr(args, "prerelease", None)
    has_filter = draft is not None or prerelease is not None
    limit: int = 0 if has_filter else (args.limit or 30)
    releases = adapter.list_releases(limit=limit)
    if draft is not None:
        releases = [r for r in releases if r.draft == draft]
    if prerelease is not None:
        releases = [r for r in releases if r.prerelease == prerelease]
    if has_filter and args.limit:
        releases = releases[: args.limit]
    output(releases, fmt=fmt, fields=["tag", "title", "draft", "prerelease"], jq=jq)


def handle_create(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo release create のハンドラ。"""
    tag = (args.tag or "").strip()
    if not tag:
        raise ConfigError(_("tag must not be empty. Use 'gfo release create <tag>'."))
    adapter = get_adapter()
    title = (args.title or "").strip() or tag
    notes_file = getattr(args, "notes_file", None)
    if args.notes and notes_file:
        raise ConfigError(_("--notes and --notes-file are mutually exclusive."))
    notes = args.notes or ""
    if notes_file:
        notes = read_file_arg(notes_file)
    release = adapter.create_release(
        tag=tag,
        title=title,
        notes=notes,
        draft=args.draft,
        prerelease=args.prerelease,
        target=getattr(args, "target", None),
        generate_notes=getattr(args, "generate_notes", False),
    )
    output(release, fmt=fmt, jq=jq)
    if getattr(args, "web", False):
        import webbrowser

        webbrowser.open(release.url)


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
    adapter = get_adapter()
    is_web = getattr(args, "web", False)
    if getattr(args, "latest", False):
        release = adapter.get_latest_release()
        tag = release.tag
    else:
        tag = (getattr(args, "tag", None) or "").strip()
        if not tag:
            raise ConfigError(_("tag must not be empty. Specify a tag or use --latest."))
        release = None
    if is_web:
        open_in_browser(adapter, "release", tag)
        return
    if release is None:
        release = adapter.get_release(tag=tag)
    output(release, fmt=fmt, jq=jq)


def handle_edit(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo release edit のハンドラ。"""
    tag = (args.tag or "").strip()
    if not tag:
        raise ConfigError(_("tag must not be empty."))
    adapter = get_adapter()
    notes_file = getattr(args, "notes_file", None)
    if args.notes and notes_file:
        raise ConfigError(_("--notes and --notes-file are mutually exclusive."))
    notes = args.notes
    if notes_file:
        notes = read_file_arg(notes_file)
    release = adapter.update_release(
        tag=tag,
        title=args.title,
        notes=notes,
        draft=args.draft,
        prerelease=args.prerelease,
        new_tag=getattr(args, "new_tag", None),
        target=getattr(args, "target", None),
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
    elif action == "edit":
        _handle_asset_edit(args, fmt=fmt, jq=jq)
    elif action == "delete":
        _handle_asset_delete(args, fmt=fmt, jq=jq)
    else:
        raise ConfigError(_("Specify a subcommand: list, upload, download, edit, delete"))


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
    import os
    from pathlib import Path

    adapter = get_adapter()
    output_dir = getattr(args, "dir", ".") or "."
    asset_id = getattr(args, "asset_id", None)
    pattern = getattr(args, "pattern", None)

    if asset_id:
        # asset_id 単体指定はメタ GET 経由 (download_url が呼び出し側で未知のため)
        path = adapter.download_release_asset(
            tag=args.tag,
            asset_id=asset_id,
            output_dir=output_dir,
        )
        print(_("Downloaded: {path}").format(path=path))
    elif pattern:
        # --pattern 経路は list_release_assets で取得済みの download_url を直接使う。
        # 旧実装は match 毎に download_release_asset を呼んでメタ情報を再取得していたが、
        # N+1 GET になるため download_url を直接 client.download_file に渡す。
        assets = adapter.list_release_assets(tag=args.tag)
        matched = [a for a in assets if fnmatch.fnmatch(a.name, pattern)]
        if not matched:
            raise ConfigError(_("No assets match pattern '{pattern}'.").format(pattern=pattern))
        os.makedirs(output_dir, exist_ok=True)
        for a in matched:
            # サーバ由来のアセット名をそのまま join すると output_dir 外へ書き込まれ得る
            # （悪意ある/侵害された forge が "../.." 等を返すケース）。asset_id 経路と
            # 同様に basename + is_relative_to で output_dir 内に閉じ込める。
            asset_name = os.path.basename(a.name)
            output_path = os.path.join(output_dir, asset_name)
            if not Path(output_path).resolve().is_relative_to(Path(output_dir).resolve()):
                raise GfoError(_("Invalid asset name: {name}").format(name=a.name))
            adapter.client.download_file(a.download_url, output_path)
            print(_("Downloaded: {path}").format(path=output_path))
    else:
        raise ConfigError(_("Specify --asset-id or --pattern."))


def _handle_asset_edit(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    adapter = get_adapter()
    asset = adapter.update_release_asset(
        tag=args.tag,
        asset_id=args.asset_id,
        name=getattr(args, "name", None),
    )
    output(asset, fmt=fmt, jq=jq)


def _handle_asset_delete(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    adapter = get_adapter()
    adapter.delete_release_asset(tag=args.tag, asset_id=args.asset_id)
    print(_("Deleted asset '{asset_id}'.").format(asset_id=args.asset_id))
