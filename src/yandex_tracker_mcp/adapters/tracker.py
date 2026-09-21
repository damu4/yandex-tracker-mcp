from __future__ import annotations

from typing import Any, ClassVar

import httpx

from yandex_tracker_mcp.domain.exceptions import TrackerError
from yandex_tracker_mcp.domain.issue import (
    CommentDraft,
    Issue,
    IssueComment,
    IssueDraft,
    IssueKey,
    IssueLink,
    IssueListItem,
    ProjectId,
)


class TrackerAuth:
    def __init__(self, token: str, org_id: str) -> None:
        if not token or not org_id:
            raise TrackerError(
                'YANDEX_TRACKER_TOKEN and YANDEX_TRACKER_ORG_ID must be set in the environment.',
                code='MISSING_CREDENTIALS',
            )
        self._token = token
        self._org_id = org_id

    def headers(self) -> dict[str, str]:
        if self._token.startswith(('t1.', 't2.')):
            return {
                'Authorization': f'Bearer {self._token}',
                'X-Cloud-Org-ID': self._org_id,
            }
        return {
            'Authorization': f'OAuth {self._token}',
            'X-Org-ID': self._org_id,
        }


class TrackerApiError(TrackerError):
    AUTH_STATUSES: ClassVar[frozenset[int]] = frozenset({401, 403, 404})

    @classmethod
    def from_response(cls, response: httpx.Response, path: str) -> TrackerApiError:
        detail = cls._detail(response)
        if response.status_code == 401:
            return cls(
                'Tracker rejected credentials (401). '
                'Update YANDEX_TRACKER_TOKEN in .env; IAM tokens expire quickly.'
                + (f' Details: {detail}' if detail else ''),
                code='UNAUTHORIZED',
            )
        if response.status_code == 403:
            return cls(
                'Tracker denied access (403). '
                'Check YANDEX_TRACKER_TOKEN and YANDEX_TRACKER_ORG_ID in .env '
                '(Administration -> Organizations -> ID in Tracker). '
                'The token must belong to the same organization.' + (f' Details: {detail}' if detail else ''),
                code='FORBIDDEN',
            )
        if response.status_code == 404:
            return cls(f'Issue not found: {path}', code='NOT_FOUND')
        suffix = f': {detail}' if detail else ''
        return cls(f'Tracker API error {response.status_code} for {path}{suffix}', code='TRACKER_API_ERROR')

    @staticmethod
    def _detail(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        messages = payload.get('errorMessages') or payload.get('errors') if isinstance(payload, dict) else None
        if isinstance(messages, list) and messages:
            return '; '.join(str(item) for item in messages)
        if isinstance(messages, dict) and messages:
            return '; '.join(f'{key}: {value}' for key, value in messages.items())
        return response.text.strip()[:200]


class TrackerClient:
    API_BASE: ClassVar[str] = 'https://api.tracker.yandex.net/v3/'
    PAGE_SIZE: ClassVar[int] = 50

    def __init__(
        self,
        token: str,
        org_id: str,
        *,
        timeout: float = 20,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = httpx.Client(
            base_url=self.API_BASE,
            headers=TrackerAuth(token, org_id).headers(),
            timeout=timeout,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> TrackerClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def get_issue(self, issue: str, *, with_comments: bool = True) -> Issue:
        key = IssueKey.parse(issue)
        raw = self._request_json('GET', f'issues/{key}')
        comments = self._list_comments(key.value) if with_comments else []
        return Issue.from_tracker(raw, comments)

    def create_issue(self, draft: IssueDraft, *, queue: str) -> Issue:
        queue_key = queue.strip()
        if not queue_key:
            raise TrackerError(
                'Queue must not be empty. Pass queue or set YANDEX_TRACKER_QUEUE.',
                code='MISSING_QUEUE',
            )
        raw = self._request_json('POST', 'issues', json=draft.to_tracker_payload(queue=queue_key))
        return Issue.from_tracker(raw)

    def update_issue(self, issue: str, draft: IssueDraft) -> Issue:
        key = IssueKey.parse(issue)
        raw = self._request_json('PATCH', f'issues/{key}', json=draft.to_tracker_payload())
        return Issue.from_tracker(raw)

    def create_link(self, issue: str, *, target: str, relationship: str = IssueLink.HAS_EPIC) -> IssueLink:
        key = IssueKey.parse(issue)
        target_key = IssueKey.parse(target)
        raw = self._request_json(
            'POST',
            f'issues/{key}/links',
            json={'relationship': relationship, 'issue': target_key.value},
        )
        return IssueLink.from_tracker(raw)

    def list_links(self, issue: str) -> tuple[IssueKey, tuple[IssueLink, ...]]:
        key = IssueKey.parse(issue)
        payload = self._request_json('GET', f'issues/{key}/links')
        items = payload if isinstance(payload, list) else payload.get('items', [])
        return key, tuple(IssueLink.from_tracker(item) for item in items)

    def list_epic_issues(self, issue: str) -> tuple[IssueKey, tuple[IssueListItem, ...]]:
        key = IssueKey.parse(issue)
        items = self._search_issues(query=f'epic: "{key.value}"')
        return key, tuple(IssueListItem.from_tracker(item) for item in items)

    def list_project_epics(self, project: str) -> tuple[ProjectId, tuple[IssueListItem, ...]]:
        project_id = ProjectId.parse(project)
        if project_id.is_numeric:
            items = self._search_issues(filter={'type': 'epic', 'project': int(project_id.value)})
        else:
            items = self._search_issues(query=project_id.epic_search_query())
        return project_id, tuple(IssueListItem.from_tracker(item) for item in items)

    def list_comments(self, issue: str) -> tuple[IssueKey, tuple[IssueComment, ...]]:
        key = IssueKey.parse(issue)
        comments = tuple(IssueComment.from_tracker(item) for item in self._list_comments(key.value))
        return key, comments

    def create_comment(self, issue: str, draft: CommentDraft) -> IssueComment:
        key = IssueKey.parse(issue)
        raw = self._request_json('POST', f'issues/{key}/comments', json=draft.to_tracker_payload())
        return IssueComment.from_tracker(raw)

    def update_comment(self, issue: str, comment_id: str | int, draft: CommentDraft) -> IssueComment:
        key = IssueKey.parse(issue)
        parsed_id = CommentDraft.parse_id(comment_id)
        raw = self._request_json(
            'PATCH',
            f'issues/{key}/comments/{parsed_id}',
            json=draft.to_tracker_payload(),
        )
        return IssueComment.from_tracker(raw)

    def _request_json(self, method: str, path: str, **kwargs: Any) -> Any:
        response = self._client.request(method, path.lstrip('/'), **kwargs)
        self._raise_for_status(response, path)
        return response.json()

    @staticmethod
    def _raise_for_status(response: httpx.Response, path: str) -> None:
        if response.status_code in TrackerApiError.AUTH_STATUSES:
            raise TrackerApiError.from_response(response, path)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise TrackerApiError.from_response(exc.response, path) from exc

    def _list_comments(self, issue_key: str) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        page = 1
        while True:
            response = self._client.get(
                f'issues/{issue_key}/comments',
                params={'page': page, 'perPage': self.PAGE_SIZE},
            )
            self._raise_for_status(response, f'comments of {issue_key}')
            payload = response.json()
            items = payload if isinstance(payload, list) else payload.get('items', [])
            if not items:
                break
            result.extend(items)
            next_page = self._next_page(response, page=page, item_count=len(items))
            if next_page is None:
                break
            page = next_page
        return result

    def _search_issues(
        self,
        *,
        query: str | None = None,
        filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        body: dict[str, Any] = {}
        if query is not None:
            body['query'] = query
        if filter is not None:
            body['filter'] = filter
        result: list[dict[str, Any]] = []
        page = 1
        while True:
            response = self._client.post(
                'issues/_search',
                params={'page': page, 'perPage': self.PAGE_SIZE},
                json=body,
            )
            self._raise_for_status(response, 'issues/_search')
            payload = response.json()
            items = payload if isinstance(payload, list) else payload.get('items', [])
            if not items:
                break
            result.extend(items)
            next_page = self._next_page(response, page=page, item_count=len(items))
            if next_page is None:
                break
            page = next_page
        return result

    def _next_page(self, response: httpx.Response, *, page: int, item_count: int) -> int | None:
        if 'X-Next-Page' in response.headers:
            next_page = response.headers.get('X-Next-Page')
            return int(next_page) if next_page else None
        if item_count < self.PAGE_SIZE:
            return None
        return page + 1
