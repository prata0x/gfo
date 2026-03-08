"""Forgejo アダプター。GiteaAdapter を継承し、service_name のみオーバーライドする。"""

from __future__ import annotations

from .gitea import GiteaAdapter
from .registry import register


@register("forgejo")
class ForgejoAdapter(GiteaAdapter):
    service_name = "Forgejo"
