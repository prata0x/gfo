from __future__ import annotations

import dataclasses

import pytest

from gfo.adapter.base import Issue, Label, Milestone, PullRequest, Release, Repository


class TestPullRequest:
    def test_create(self):
        pr = PullRequest(
            number=1,
            title="feat: add login",
            body="Implements login flow",
            state="open",
            author="alice",
            source_branch="feat/login",
            target_branch="main",
            draft=False,
            url="https://example.com/pr/1",
            created_at="2026-01-01T00:00:00Z",
            updated_at=None,
        )
        assert pr.number == 1
        assert pr.title == "feat: add login"
        assert pr.updated_at is None

    def test_frozen(self):
        pr = PullRequest(
            number=1,
            title="t",
            body=None,
            state="open",
            author="a",
            source_branch="b",
            target_branch="main",
            draft=False,
            url="u",
            created_at="c",
            updated_at=None,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            pr.title = "changed"  # type: ignore[misc]


class TestIssue:
    def test_create(self):
        issue = Issue(
            number=42,
            title="Bug report",
            body=None,
            state="open",
            author="bob",
            assignees=["alice"],
            labels=["bug", "high"],
            url="https://example.com/issue/42",
            created_at="2026-01-01T00:00:00Z",
        )
        assert issue.number == 42
        assert issue.labels == ["bug", "high"]
        assert issue.body is None

    def test_frozen(self):
        issue = Issue(
            number=1,
            title="t",
            body=None,
            state="open",
            author="a",
            assignees=[],
            labels=[],
            url="u",
            created_at="c",
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            issue.state = "closed"  # type: ignore[misc]


class TestRepository:
    def test_create(self):
        repo = Repository(
            name="gfo",
            full_name="owner/gfo",
            description="A tool",
            private=False,
            default_branch="main",
            clone_url="https://example.com/gfo.git",
            url="https://example.com/gfo",
        )
        assert repo.full_name == "owner/gfo"
        assert repo.private is False

    def test_optional_fields(self):
        repo = Repository(
            name="gfo",
            full_name="owner/gfo",
            description=None,
            private=True,
            default_branch=None,
            clone_url="https://example.com/gfo.git",
            url="https://example.com/gfo",
        )
        assert repo.description is None
        assert repo.default_branch is None

    def test_frozen(self):
        repo = Repository(
            name="gfo",
            full_name="owner/gfo",
            description=None,
            private=False,
            default_branch="main",
            clone_url="c",
            url="u",
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            repo.name = "other"  # type: ignore[misc]


class TestRelease:
    def test_create(self):
        release = Release(
            tag="v1.0.0",
            title="Release 1.0.0",
            body="First release",
            draft=False,
            prerelease=False,
            url="https://example.com/release/v1.0.0",
            created_at="2026-01-01T00:00:00Z",
        )
        assert release.tag == "v1.0.0"
        assert release.draft is False

    def test_frozen(self):
        release = Release(
            tag="v1.0.0",
            title="t",
            body=None,
            draft=False,
            prerelease=False,
            url="u",
            created_at="c",
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            release.tag = "v2.0.0"  # type: ignore[misc]


class TestLabel:
    def test_create(self):
        label = Label(name="bug", color="ff0000", description="Bug report")
        assert label.name == "bug"
        assert label.color == "ff0000"

    def test_optional_fields(self):
        label = Label(name="bug", color=None, description=None)
        assert label.color is None
        assert label.description is None

    def test_frozen(self):
        label = Label(name="bug", color=None, description=None)
        with pytest.raises(dataclasses.FrozenInstanceError):
            label.name = "feature"  # type: ignore[misc]


class TestMilestone:
    def test_create(self):
        ms = Milestone(
            number=1,
            title="v1.0",
            description="First milestone",
            state="open",
            due_date="2026-06-01",
        )
        assert ms.number == 1
        assert ms.title == "v1.0"

    def test_optional_fields(self):
        ms = Milestone(
            number=2,
            title="v2.0",
            description=None,
            state="closed",
            due_date=None,
        )
        assert ms.description is None
        assert ms.due_date is None

    def test_frozen(self):
        ms = Milestone(
            number=1, title="v1.0", description=None, state="open", due_date=None
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            ms.state = "closed"  # type: ignore[misc]
