from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PullRequest:
    number: int
    title: str
    body: str | None
    state: str          # "open" | "closed" | "merged"
    author: str
    source_branch: str
    target_branch: str
    draft: bool
    url: str
    created_at: str     # ISO 8601
    updated_at: str | None


@dataclass(frozen=True, slots=True)
class Issue:
    number: int
    title: str
    body: str | None
    state: str          # "open" | "closed"
    author: str
    assignees: list[str]
    labels: list[str]
    url: str
    created_at: str


@dataclass(frozen=True, slots=True)
class Repository:
    name: str
    full_name: str      # "owner/repo"
    description: str | None
    private: bool
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
    state: str          # "open" | "closed"
    due_date: str | None
