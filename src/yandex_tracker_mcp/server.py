from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from mcp.server.fastmcp import FastMCP

from yandex_tracker_mcp.adapters.tracker import TrackerClient
from yandex_tracker_mcp.application.issue_service import IssueService
from yandex_tracker_mcp.domain.exceptions import TrackerError
from yandex_tracker_mcp.settings import Settings


class TrackerMcp:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings

    def get_issue(self, issue: str) -> dict[str, Any]:
        with self._service() as service:
            return service.get_issue(issue)

    def create_issue(
        self,
        issue_type: str,
        summary: str,
        description: str,
        queue: str | None = None,
        epic: str | None = None,
        story_points: int | float | None = None,
    ) -> dict[str, Any]:
        with self._service() as service:
            return service.create_issue(
                issue_type=issue_type,
                summary=summary,
                description=description,
                queue=queue,
                epic=epic,
                story_points=story_points,
            )

    def update_issue(
        self,
        issue: str,
        issue_type: str | None = None,
        summary: str | None = None,
        description: str | None = None,
        story_points: int | float | None = None,
        set_story_points: bool = False,
    ) -> dict[str, Any]:
        with self._service() as service:
            return service.update_issue(
                issue=issue,
                issue_type=issue_type,
                summary=summary,
                description=description,
                story_points=story_points,
                set_story_points=set_story_points,
            )

    def update_issue_status(
        self,
        issue: str,
        status: str,
        resolution: str | None = None,
    ) -> dict[str, Any]:
        with self._service() as service:
            return service.update_issue_status(issue, status, resolution)

    def get_epic_issues(self, issue: str) -> dict[str, Any]:
        with self._service() as service:
            return service.get_epic_issues(issue)

    def get_project_epics(self, project: str) -> dict[str, Any]:
        with self._service() as service:
            return service.get_project_epics(project)

    def get_issue_links(self, issue: str) -> dict[str, Any]:
        with self._service() as service:
            return service.get_issue_links(issue)

    def link_issue(
        self,
        issue: str,
        target: str,
        relationship: str = 'has epic',
    ) -> dict[str, Any]:
        with self._service() as service:
            return service.link_issue(issue, target=target, relationship=relationship)

    def get_comments(self, issue: str) -> dict[str, Any]:
        with self._service() as service:
            return service.get_comments(issue)

    def create_comment(self, issue: str, text: str) -> dict[str, Any]:
        with self._service() as service:
            return service.create_comment(issue, text)

    def update_comment(self, issue: str, comment_id: str, text: str) -> dict[str, Any]:
        with self._service() as service:
            return service.update_comment(issue, comment_id, text)

    @contextmanager
    def _service(self) -> Iterator[IssueService]:
        settings = self._settings or Settings.load()
        try:
            with TrackerClient(settings.yandex_tracker_token, settings.yandex_tracker_org_id) as client:
                yield IssueService(client, default_queue=settings.yandex_tracker_queue)
        except TrackerError as exc:
            raise RuntimeError(str(exc)) from exc


mcp = FastMCP('yandex-tracker')
_tools = TrackerMcp()


@mcp.tool()
def get_issue(issue: str) -> dict[str, Any]:
    """Read a Yandex Tracker issue by key or URL.

    Returns only the issue key, type, status, story points, title, description, parent/epic refs, and comments
    (id, text, createdAt, updatedAt). Does not return assignee, authors, or other personal data.

    Args:
        issue: Issue key (LGS-584) or Tracker URL (https://tracker.yandex.ru/LGS-584).
    """
    return _tools.get_issue(issue)


@mcp.tool()
def create_issue(
    issue_type: str,
    summary: str,
    description: str,
    queue: str | None = None,
    epic: str | None = None,
    story_points: float | None = None,
) -> dict[str, Any]:
    """Create a Yandex Tracker issue.

    Backend issues get the title prefix "BE:" and type "Backend".
    Frontend issues get the title prefix "FE:" and type "Frontend".
    Pass epic to attach the new issue to an epic (Tracker link type "has epic").
    Types: Backend / be, Frontend / fe, QA / qa, Ошибка / bug, Автотесты / autotest,
    Задача / task, or the exact Tracker type name.

    Args:
        issue_type: Issue type (backend / Frontend / QA / Ошибка / Автотесты / Задача, or a Tracker type name).
        summary: Issue title.
        description: Issue body text.
        queue: Queue key. Defaults to YANDEX_TRACKER_QUEUE (LGS).
        epic: Epic key or URL to attach (LGS-275).
        story_points: Story Points estimate, if known.
    """
    return _tools.create_issue(
        issue_type=issue_type,
        summary=summary,
        description=description,
        queue=queue,
        epic=epic,
        story_points=story_points,
    )


@mcp.tool()
def update_issue(
    issue: str,
    issue_type: str | None = None,
    summary: str | None = None,
    description: str | None = None,
    story_points: float | None = None,
) -> dict[str, Any]:
    """Update a Yandex Tracker issue type, title, description, and/or Story Points.

    Backend issues keep or receive the title prefix "BE:"; frontend issues keep or receive "FE:".
    Changing the type away from Backend or Frontend removes that type's prefix.
    Types: Backend / be, Frontend / fe, QA / qa, Ошибка / bug, Автотесты / autotest,
    Задача / task, or the exact Tracker type name.

    Args:
        issue: Issue key (LGS-584) or Tracker URL.
        issue_type: New issue type, if changing it (Backend, Frontend, QA, Ошибка, Задача, ...).
        summary: New title, if changing it.
        description: New body text, if changing it.
        story_points: New Story Points estimate, if changing it.
    """
    return _tools.update_issue(
        issue=issue,
        issue_type=issue_type,
        summary=summary,
        description=description,
        story_points=story_points,
        set_story_points=story_points is not None,
    )


@mcp.tool()
def update_issue_status(
    issue: str,
    status: str,
    resolution: str | None = None,
) -> dict[str, Any]:
    """Move a Yandex Tracker issue to another workflow status.

    Pass the target status name (В работе), status key (inProgress), or transition id.
    If the issue is already in that status, it is returned unchanged.
    Closing transitions often require a resolution key such as fixed.

    Args:
        issue: Issue key (LGS-584) or Tracker URL.
        status: Target status display, status key, or transition id.
        resolution: Resolution key, when the transition requires one.
    """
    return _tools.update_issue_status(issue, status, resolution)


@mcp.tool()
def get_epic_issues(issue: str) -> dict[str, Any]:
    """List issues that belong to a Yandex Tracker epic.

    Returns keys, titles, types, statuses, and Story Points. Does not return assignee or other personal data.

    Args:
        issue: Epic key (DISC-869) or Tracker URL (https://tracker.yandex.ru/DISC-869).
    """
    return _tools.get_epic_issues(issue)


@mcp.tool()
def get_project_epics(project: str) -> dict[str, Any]:
    """List Epic issues that belong to a Yandex Tracker project.

    Returns keys, titles, types, statuses, and Story Points. Does not return assignee or other personal data.

    Args:
        project: Project ID (5787) or Tracker URL (https://tracker.yandex.ru/pages/projects/5787/).
    """
    return _tools.get_project_epics(project)


@mcp.tool()
def get_issue_links(issue: str) -> dict[str, Any]:
    """Read Yandex Tracker issue links: epic, subtask, relates, depends, duplicate.

    Returns relationship type, direction, linked key, title, and status.
    Does not return assignee, authors, or other personal data.

    Args:
        issue: Issue key (LGS-584) or Tracker URL.
    """
    return _tools.get_issue_links(issue)


@mcp.tool()
def link_issue(
    issue: str,
    target: str,
    relationship: str = 'has epic',
) -> dict[str, Any]:
    """Link a Yandex Tracker issue to another issue.

    Default relationship is "has epic" (attach issue to an epic).
    Other Tracker types: relates, depends on, is dependent by, is subtask for,
    is parent task for, duplicates, is duplicated by, is epic of.

    Args:
        issue: Issue key or URL to link from (LGS-610).
        target: Linked issue key or URL (epic LGS-275).
        relationship: Tracker link type. Defaults to has epic.
    """
    return _tools.link_issue(issue, target=target, relationship=relationship)


@mcp.tool()
def get_comments(issue: str) -> dict[str, Any]:
    """List comments on a Yandex Tracker issue.

    Returns comment id, text, createdAt, and updatedAt. Does not return authors or other personal data.

    Args:
        issue: Issue key (LGS-584) or Tracker URL.
    """
    return _tools.get_comments(issue)


@mcp.tool()
def create_comment(issue: str, text: str) -> dict[str, Any]:
    """Add a comment to a Yandex Tracker issue.

    Returns the created comment id, text, createdAt, and updatedAt. Does not return authors.

    Args:
        issue: Issue key (LGS-584) or Tracker URL.
        text: Comment body. Must not be empty.
    """
    return _tools.create_comment(issue, text)


@mcp.tool()
def update_comment(issue: str, comment_id: str, text: str) -> dict[str, Any]:
    """Edit an existing Yandex Tracker comment.

    Returns the updated comment id, text, createdAt, and updatedAt. Does not return authors.

    Args:
        issue: Issue key (LGS-584) or Tracker URL.
        comment_id: Comment id from get_comments or get_issue.
        text: New comment body. Must not be empty.
    """
    return _tools.update_comment(issue, comment_id, text)


async def _run_stdio() -> None:
    from mcp.server.lowlevel.server import NotificationOptions
    from mcp.server.stdio import stdio_server
    from mcp.types import ClientNotification, InitializedNotification

    lowlevel = mcp._mcp_server
    lowlevel.version = '0.2.0'
    original = lowlevel._handle_message

    async def handle_message(
        message: object,
        session: object,
        lifespan_context: object,
        raise_exceptions: bool = False,
    ) -> None:
        await original(message, session, lifespan_context, raise_exceptions)
        if isinstance(message, ClientNotification) and isinstance(message.root, InitializedNotification):
            await session.send_tool_list_changed()  # type: ignore[union-attr]

    lowlevel._handle_message = handle_message  # type: ignore[method-assign]
    async with stdio_server() as (read_stream, write_stream):
        await lowlevel.run(
            read_stream,
            write_stream,
            lowlevel.create_initialization_options(
                notification_options=NotificationOptions(tools_changed=True),
            ),
        )


def main() -> None:
    import anyio

    anyio.run(_run_stdio)


if __name__ == '__main__':
    main()
