from __future__ import annotations

from typing import Any

from yandex_tracker_mcp.adapters.tracker import TrackerClient
from yandex_tracker_mcp.domain.issue import CommentDraft, IssueDraft


class IssueService:
    def __init__(self, client: TrackerClient, *, default_queue: str) -> None:
        self._client = client
        self._default_queue = default_queue

    def get_issue(self, issue: str) -> dict[str, Any]:
        return self._client.get_issue(issue).to_payload()

    def create_issue(
        self,
        issue_type: str,
        summary: str,
        description: str,
        queue: str | None = None,
        epic: str | None = None,
        story_points: int | float | None = None,
    ) -> dict[str, Any]:
        draft = IssueDraft.for_create(
            issue_type=issue_type,
            summary=summary,
            description=description,
            epic=epic,
            story_points=story_points,
        )
        return self._client.create_issue(draft, queue=queue or self._default_queue).to_payload()

    def update_issue(
        self,
        issue: str,
        issue_type: str | None = None,
        summary: str | None = None,
        description: str | None = None,
        story_points: int | float | None = None,
        set_story_points: bool = False,
    ) -> dict[str, Any]:
        current = self._client.get_issue(issue, with_comments=False)
        draft = IssueDraft.for_update(
            current,
            issue_type=issue_type,
            summary=summary,
            description=description,
            story_points=story_points,
            set_story_points=set_story_points,
        )
        return self._client.update_issue(issue, draft).to_payload()

    def get_epic_issues(self, issue: str) -> dict[str, Any]:
        key, issues = self._client.list_epic_issues(issue)
        return {
            'epic': key.value,
            'issues': [item.to_payload() for item in issues],
        }

    def get_project_epics(self, project: str) -> dict[str, Any]:
        project_id, epics = self._client.list_project_epics(project)
        return {
            'project': project_id.value,
            'epics': [item.to_payload() for item in epics],
        }

    def get_issue_links(self, issue: str) -> dict[str, Any]:
        key, links = self._client.list_links(issue)
        return {
            'key': key.value,
            'links': [link.to_payload() for link in links],
        }

    def link_issue(
        self,
        issue: str,
        target: str,
        relationship: str = 'has epic',
    ) -> dict[str, Any]:
        self._client.create_link(issue, target=target, relationship=relationship)
        return self._client.get_issue(issue, with_comments=False).to_payload()

    def get_comments(self, issue: str) -> dict[str, Any]:
        key, comments = self._client.list_comments(issue)
        return {
            'key': key.value,
            'comments': [comment.to_payload() for comment in comments],
        }

    def create_comment(self, issue: str, text: str) -> dict[str, Any]:
        return self._client.create_comment(issue, CommentDraft.parse(text)).to_payload()

    def update_comment(self, issue: str, comment_id: str, text: str) -> dict[str, Any]:
        return self._client.update_comment(issue, comment_id, CommentDraft.parse(text)).to_payload()
