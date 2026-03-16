"""gfo browse サブコマンドのハンドラ。"""

import webbrowser

from gfo.commands import get_adapter


def handle_browse(args, *, fmt: str) -> None:
    adapter = get_adapter()
    resource = "repo"
    number = None
    if getattr(args, "pr", None) is not None:
        resource, number = "pr", args.pr
    elif getattr(args, "issue", None) is not None:
        resource, number = "issue", args.issue
    elif getattr(args, "settings", False):
        resource = "settings"

    url = adapter.get_web_url(resource, number)

    if getattr(args, "print", False):
        print(url)
    else:
        webbrowser.open(url)
