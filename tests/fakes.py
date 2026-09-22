from __future__ import annotations

import json
import re
from typing import Any

import httpx


class FakeTrackerApi:
    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.issues: dict[str, dict[str, Any]] = {}
        self.comments: dict[str, list[dict[str, Any]]] = {}
        self.links: dict[str, list[dict[str, Any]]] = {}
        self.transitions: dict[str, list[dict[str, Any]]] = {}
        self._created = 0
        self.status_overrides: dict[str, int] = {}
        self.error_payloads: dict[str, dict[str, Any]] = {}

    def add_issue(
        self,
        key: str,
        *,
        summary: str,
        description: str = '',
        issue_type: str = 'task',
        status: str = 'Open',
        parent: str | None = None,
        epic: str | None = None,
        project: str | None = None,
        extra: dict[str, Any] | None = None,
        story_points: int | float | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            'key': key,
            'summary': summary,
            'description': description,
            'type': {'key': issue_type.casefold(), 'name': issue_type, 'display': issue_type},
            'status': {'key': status.casefold(), 'display': status},
            'assignee': {'login': 'ivan', 'display': 'Ivan'},
            'createdBy': {'login': 'petr'},
        }
        if parent:
            parent_issue = self.issues.get(parent, {})
            payload['parent'] = {'key': parent, 'display': parent_issue.get('summary', parent)}
        if epic:
            epic_issue = self.issues.get(epic, {})
            payload['epic'] = {'key': epic, 'display': epic_issue.get('summary', epic)}
        if project:
            payload['project'] = {
                'primary': {
                    'id': project,
                    'key': project,
                    'display': project,
                },
            }
        if story_points is not None:
            payload['storyPoints'] = story_points
        if extra:
            payload.update(extra)
        self.issues[key] = payload

    def add_comment(
        self,
        key: str,
        text: str,
        created_at: str,
        *,
        author: str = 'ivan',
        comment_id: int | None = None,
        updated_at: str | None = None,
    ) -> dict[str, Any]:
        items = self.comments.setdefault(key, [])
        cid = comment_id if comment_id is not None else len(items) + 1
        payload = {
            'id': cid,
            'longId': str(cid),
            'text': text,
            'createdAt': created_at,
            'updatedAt': updated_at or created_at,
            'createdBy': {'login': author},
            'updatedBy': {'login': author},
        }
        items.append(payload)
        return payload

    def add_transition(
        self,
        key: str,
        *,
        transition_id: str,
        display: str,
        status: str,
        status_key: str | None = None,
    ) -> None:
        self.transitions.setdefault(key, []).append(
            {
                'id': transition_id,
                'display': display,
                'to': {'key': status_key or status.casefold(), 'display': status},
            },
        )

    def add_link(
        self,
        issue_key: str,
        *,
        relationship: str,
        direction: str,
        object_key: str,
        object_summary: str,
        status: str = 'Open',
        outward: str = '',
        inward: str = '',
    ) -> None:
        self.links.setdefault(issue_key, []).append(
            {
                'id': len(self.links.get(issue_key, [])) + 1,
                'type': {
                    'id': relationship,
                    'inward': inward,
                    'outward': outward,
                },
                'direction': direction,
                'object': {'key': object_key, 'display': object_summary},
                'status': {'key': status.casefold(), 'display': status},
                'assignee': {'login': 'ivan', 'display': 'Ivan'},
                'createdBy': {'login': 'petr'},
                'updatedBy': {'login': 'olga'},
            },
        )

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self)

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path.rstrip('/')
        override = self.status_overrides.get(f'{request.method} {path}') or self.status_overrides.get(path)
        if override:
            return httpx.Response(override, json=self.error_payloads.get(path, {'error': 'failed'}))

        if request.method == 'GET' and path.endswith('/transitions'):
            return self._transitions_response(path)
        if request.method == 'POST' and path.endswith('/_execute') and '/transitions/' in path:
            return self._execute_transition_response(path)
        if request.method == 'GET' and path.endswith('/comments'):
            return self._comments_response(request, path)
        if request.method == 'POST' and path.endswith('/comments'):
            return self._create_comment_response(request, path)
        if request.method == 'PATCH' and '/comments/' in path:
            return self._update_comment_response(request, path)
        if request.method == 'GET' and path.endswith('/links'):
            return self._links_response(path)
        if request.method == 'POST' and path.endswith('/links'):
            return self._create_link_response(request, path)
        if request.method == 'GET' and '/issues/' in path:
            return self._get_issue_response(path)
        if request.method == 'POST' and path.endswith('/_search'):
            return self._search_response(request)
        if request.method == 'POST' and path.endswith('/issues'):
            return self._create_issue_response(request)
        if request.method == 'PATCH' and '/issues/' in path:
            return self._update_issue_response(request, path)
        return httpx.Response(404, json={'error': 'not found'})

    def _get_issue_response(self, path: str) -> httpx.Response:
        key = path.rsplit('/', 1)[-1]
        issue = self.issues.get(key)
        if issue is None:
            return httpx.Response(404, json={'error': 'not found'})
        return httpx.Response(200, json=issue)

    def _create_issue_response(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        self._created += 1
        queue = body.get('queue', 'LGS')
        key = f'{queue}-{self._created}'
        type_name = self._type_name(body.get('type'))
        self.add_issue(
            key,
            summary=body.get('summary', ''),
            description=body.get('description', ''),
            issue_type=type_name,
            story_points=body.get('storyPoints'),
        )
        for link in body.get('links') or []:
            if link.get('relationship') == 'has epic':
                epic_key = str(link.get('issue') or '')
                epic_issue = self.issues.get(epic_key, {})
                self.issues[key]['epic'] = {
                    'key': epic_key,
                    'display': epic_issue.get('summary', epic_key),
                }
        return httpx.Response(201, json=self.issues[key])

    def _update_issue_response(self, request: httpx.Request, path: str) -> httpx.Response:
        key = path.rsplit('/', 1)[-1]
        issue = self.issues.get(key)
        if issue is None:
            return httpx.Response(404, json={'error': 'not found'})
        body = json.loads(request.content)
        if 'summary' in body:
            issue['summary'] = body['summary']
        if 'description' in body:
            issue['description'] = body['description']
        if 'type' in body:
            type_name = self._type_name(body['type'])
            issue['type'] = {'key': type_name.casefold(), 'name': type_name, 'display': type_name}
        if 'storyPoints' in body:
            issue['storyPoints'] = body['storyPoints']
        return httpx.Response(200, json=issue)

    def _transitions_response(self, path: str) -> httpx.Response:
        key = path.split('/issues/')[1].split('/')[0]
        if key not in self.issues:
            return httpx.Response(404, json={'error': 'not found'})
        return httpx.Response(200, json=self.transitions.get(key, []))

    def _execute_transition_response(self, path: str) -> httpx.Response:
        parts = path.split('/issues/')[1].split('/')
        key = parts[0]
        transition_id = parts[2] if len(parts) > 2 else ''
        issue = self.issues.get(key)
        if issue is None:
            return httpx.Response(404, json={'error': 'not found'})
        transition = next(
            (item for item in self.transitions.get(key, []) if item.get('id') == transition_id),
            None,
        )
        if transition is None:
            return httpx.Response(404, json={'error': 'not found'})
        issue['status'] = dict(transition['to'])
        return httpx.Response(200, json=self.transitions.get(key, []))

    def _links_response(self, path: str) -> httpx.Response:
        key = path.split('/issues/')[1].split('/')[0]
        return httpx.Response(200, json=self.links.get(key, []))

    def _create_link_response(self, request: httpx.Request, path: str) -> httpx.Response:
        key = path.split('/issues/')[1].split('/')[0]
        if key not in self.issues:
            return httpx.Response(404, json={'error': 'not found'})
        body = json.loads(request.content)
        relationship = str(body.get('relationship') or '')
        target = str(body.get('issue') or '')
        target_issue = self.issues.get(target, {})
        type_id = 'epic' if relationship == 'has epic' else relationship
        self.add_link(
            key,
            relationship=type_id,
            direction='inward',
            object_key=target,
            object_summary=str(target_issue.get('summary') or target),
            outward='Epic for' if type_id == 'epic' else relationship,
            inward='Sub-epic' if type_id == 'epic' else relationship,
        )
        if relationship == 'has epic':
            self.issues[key]['epic'] = {
                'key': target,
                'display': target_issue.get('summary', target),
            }
        return httpx.Response(201, json=self.links[key][-1])

    def _search_response(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content or b'{}')
        matches = self._matching_issues(
            query=str(body.get('query') or ''),
            filter_body=body.get('filter'),
        )
        page = int(request.url.params.get('page') or '1')
        start = page - 1
        if start >= len(matches):
            return httpx.Response(200, headers={'X-Next-Page': ''}, json=[])
        next_page = str(page + 1) if page < len(matches) else ''
        return httpx.Response(200, headers={'X-Next-Page': next_page}, json=[matches[start]])

    def _matching_issues(self, query: str, filter_body: Any) -> list[dict[str, Any]]:
        if isinstance(filter_body, dict) and filter_body.get('project') is not None:
            project_id = str(filter_body['project'])
            type_filter = str(filter_body.get('type') or 'epic')
            return [
                issue
                for issue in self.issues.values()
                if self._is_project_epic(issue, project_id=project_id, project_name='')
                and self._type_name(issue.get('type')).casefold() == type_filter.casefold()
            ]
        project_match = re.search(
            r'Type:\s*Epic\s+(?:Project:\s*(\d+)|"Project":\s*"([^"]+)")',
            query,
            re.I,
        )
        if project_match:
            project_id = project_match.group(1) or ''
            project_name = project_match.group(2) or ''
            return [
                issue
                for issue in self.issues.values()
                if self._is_project_epic(issue, project_id=project_id, project_name=project_name)
            ]
        epic_match = re.search(r'epic:\s*"([^"]+)"', query, re.I)
        epic_key = epic_match.group(1) if epic_match else ''
        return [
            issue
            for issue in self.issues.values()
            if isinstance(issue.get('epic'), dict) and issue['epic'].get('key') == epic_key
        ]

    @classmethod
    def _is_project_epic(
        cls,
        issue: dict[str, Any],
        *,
        project_id: str,
        project_name: str,
    ) -> bool:
        if cls._type_name(issue.get('type')).casefold() != 'epic':
            return False
        project = issue.get('project')
        if not isinstance(project, dict):
            return False
        primary = project.get('primary') if isinstance(project.get('primary'), dict) else project
        pid = str(primary.get('id') or primary.get('key') or '')
        display = str(primary.get('display') or primary.get('name') or '')
        if project_id:
            return pid == project_id
        return display.casefold() == project_name.casefold()

    def _comments_response(self, request: httpx.Request, path: str) -> httpx.Response:
        key = path.split('/issues/')[1].split('/')[0]
        page = int(request.url.params.get('page') or '1')
        items = self.comments.get(key, [])
        start = page - 1
        if start >= len(items):
            return httpx.Response(200, headers={'X-Next-Page': ''}, json=[])
        item = items[start]
        next_page = str(page + 1) if page < len(items) else ''
        return httpx.Response(200, headers={'X-Next-Page': next_page}, json=[item])

    def _create_comment_response(self, request: httpx.Request, path: str) -> httpx.Response:
        key = path.split('/issues/')[1].split('/')[0]
        if key not in self.issues:
            return httpx.Response(404, json={'error': 'not found'})
        body = json.loads(request.content)
        comment = self.add_comment(
            key,
            str(body.get('text') or ''),
            '2026-01-03T00:00:00.000+0000',
        )
        return httpx.Response(201, json=comment)

    def _update_comment_response(self, request: httpx.Request, path: str) -> httpx.Response:
        parts = path.split('/issues/')[1].split('/')
        key = parts[0]
        comment_id = parts[2] if len(parts) > 2 else ''
        body = json.loads(request.content)
        for item in self.comments.get(key, []):
            if str(item.get('id')) == comment_id or str(item.get('longId')) == comment_id:
                item['text'] = str(body.get('text') or item['text'])
                item['updatedAt'] = '2026-01-04T00:00:00.000+0000'
                item['updatedBy'] = {'login': 'olga'}
                return httpx.Response(200, json=item)
        return httpx.Response(404, json={'error': 'not found'})

    @staticmethod
    def _type_name(value: Any) -> str:
        if isinstance(value, dict):
            return str(value.get('name') or value.get('key') or '')
        return str(value or '')
