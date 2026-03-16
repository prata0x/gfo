#!/usr/bin/env python3
"""GIT_ASKPASS ヘルパースクリプト。

git clone 等の URL にトークンを埋め込む代わりに、
このスクリプトを GIT_ASKPASS に設定して認証情報を返す。

環境変数 GFO_GIT_TOKEN にトークンを設定して使用する。
"""

import os
import sys


def main() -> None:
    prompt = sys.argv[1] if len(sys.argv) > 1 else ""
    # Username プロンプトにはユーザー名、Password プロンプトにはトークンを返す
    if "username" in prompt.lower() or "user" in prompt.lower():
        print(os.environ.get("GFO_GIT_USERNAME", "gfo-admin"))
    else:
        print(os.environ.get("GFO_GIT_TOKEN", ""))


if __name__ == "__main__":
    main()
