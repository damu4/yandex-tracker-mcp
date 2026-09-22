from __future__ import annotations

import json

import httpx
import pytest

from tests.fakes import FakeTrackerApi
from yandex_tracker_mcp.adapters.tracker import TrackerApiError, TrackerAuth, TrackerClient
from yandex_tracker_mcp.domain.exceptions import TrackerError
from yandex_tracker_mcp.domain.issue import CommentDraft, IssueDraft, IssueStatusChange


class TestTrackerAuth:
    def test_headers__iam_token__uses_bearer_and_cloud_org(self) -> None:
        # act
        headers = TrackerAuth('t1.abc', 'org123').headers()

        # assert
        assert headers == {
            'Authorization': 'Bearer t1.abc',
            'X-Cloud-Org-ID': 'org123',
        }

    def test_headers__oauth_token__uses_oauth_and_org_id(self) -> None:
        # act
        headers = TrackerAuth('y0_abc', '123456').headers()

        # assert
        assert headers == {
            'Authorization': 'OAuth y0_abc',
            'X-Org-ID': '123456',
        }

    def test_init__empty_token__raises_tracker_error(self) -> None:
        # act / assert
        with pytest.raises(TrackerError):
            TrackerAuth('', 'org')


class TestTrackerClient:
    def test_get_issue__strips_pii_and_paginates_comments(self) -> None:
        # arrange
        api = FakeTrackerApi()
        api.add_issue('LGS-584', summary='Title', description='Body', issue_type='Backend')
        api.add_comment('LGS-584', 'First', '2026-01-01T00:00:00.000+0000')
        api.add_comment('LGS-584', 'Second', '2026-01-02T00:00:00.000+0000', author='olga')

        # act
        with TrackerClient('token', 'org', transport=api.transport()) as client:
            result = client.get_issue('https://tracker.yandex.ru/LGS-584').to_payload()

        # assert
        assert result == {
            'key': 'LGS-584',
            'summary': 'Title',
            'description': 'Body',
            'type': 'Backend',
            'status': 'Open',
            'storyPoints': None,
            'parent': None,
            'epic': None,
            'comments': [
                {
                    'id': '1',
                    'text': 'First',
                    'createdAt': '2026-01-01T00:00:00.000+0000',
                    'updatedAt': '2026-01-01T00:00:00.000+0000',
                },
                {
                    'id': '2',
                    'text': 'Second',
                    'createdAt': '2026-01-02T00:00:00.000+0000',
                    'updatedAt': '2026-01-02T00:00:00.000+0000',
                },
            ],
        }
        dumped = json.dumps(result)
        assert 'ivan' not in dumped
        assert 'petr' not in dumped
        assert 'olga' not in dumped
        assert [request.url.path for request in api.requests] == [
            '/v3/issues/LGS-584',
            '/v3/issues/LGS-584/comments',
            '/v3/issues/LGS-584/comments',
        ]

    def test_create_issue__posts_queue_type_and_title(self) -> None:
        # arrange
        api = FakeTrackerApi()
        draft = IssueDraft.for_create(
            issue_type='backend',
            summary='Add rates',
            description='Body',
        )

        # act
        with TrackerClient('token', 'org', transport=api.transport()) as client:
            result = client.create_issue(draft, queue='LGS').to_payload()

        # assert
        assert result['key'] == 'LGS-1'
        assert result['summary'] == 'BE: Add rates'
        assert result['type'] == 'Backend'
        request = api.requests[0]
        assert request.method == 'POST'
        assert request.url.path == '/v3/issues'
        assert json.loads(request.content) == {
            'queue': 'LGS',
            'summary': 'BE: Add rates',
            'description': 'Body',
            'type': {'name': 'Backend'},
        }

    def test_create_issue__with_story_points__posts_story_points(self) -> None:
        # arrange
        api = FakeTrackerApi()
        draft = IssueDraft.for_create(
            issue_type='задача',
            summary='Estimate work',
            description='Body',
            story_points=3,
        )

        # act
        with TrackerClient('token', 'org', transport=api.transport()) as client:
            result = client.create_issue(draft, queue='LGS').to_payload()

        # assert
        assert result['type'] == 'Задача'
        assert result['storyPoints'] == 3
        assert json.loads(api.requests[0].content)['storyPoints'] == 3

    def test_create_issue__with_epic__posts_has_epic_link(self) -> None:
        # arrange
        api = FakeTrackerApi()
        api.add_issue('LGS-275', summary='Calculator dictionaries', issue_type='Epic')
        draft = IssueDraft.for_create(
            issue_type='backend',
            summary='Add rates',
            description='Body',
            epic='LGS-275',
        )

        # act
        with TrackerClient('token', 'org', transport=api.transport()) as client:
            result = client.create_issue(draft, queue='LGS').to_payload()

        # assert
        assert result['epic'] == {'key': 'LGS-275', 'summary': 'Calculator dictionaries'}
        assert json.loads(api.requests[0].content)['links'] == [
            {'relationship': 'has epic', 'issue': 'LGS-275'},
        ]

    def test_create_link__posts_has_epic_and_sets_epic(self) -> None:
        # arrange
        api = FakeTrackerApi()
        api.add_issue('LGS-275', summary='Calculator dictionaries', issue_type='Epic')
        api.add_issue('LGS-610', summary='BE: Local params', issue_type='Backend')

        # act
        with TrackerClient('token', 'org', transport=api.transport()) as client:
            link = client.create_link('LGS-610', target='https://tracker.yandex.ru/LGS-275')
            result = client.get_issue('LGS-610', with_comments=False).to_payload()

        # assert
        assert link.key == 'LGS-275'
        assert link.relationship == 'epic'
        assert result['epic'] == {'key': 'LGS-275', 'summary': 'Calculator dictionaries'}
        request = api.requests[0]
        assert request.method == 'POST'
        assert request.url.path == '/v3/issues/LGS-610/links'
        assert json.loads(request.content) == {
            'relationship': 'has epic',
            'issue': 'LGS-275',
        }

    def test_update_issue__patches_type_title_and_description(self) -> None:
        # arrange
        api = FakeTrackerApi()
        api.add_issue('LGS-1', summary='Old', description='Old body', issue_type='Feature')
        draft = IssueDraft.for_create(
            issue_type='backend',
            summary='New title',
            description='New body',
        )

        # act
        with TrackerClient('token', 'org', transport=api.transport()) as client:
            result = client.update_issue('LGS-1', draft).to_payload()

        # assert
        assert result['summary'] == 'BE: New title'
        assert result['description'] == 'New body'
        assert result['type'] == 'Backend'
        request = api.requests[0]
        assert request.method == 'PATCH'
        assert json.loads(request.content)['type'] == {'name': 'Backend'}

    def test_update_issue__patches_story_points(self) -> None:
        # arrange
        api = FakeTrackerApi()
        api.add_issue('LGS-1', summary='Old', description='Old body', issue_type='Задача', story_points=1)

        # act
        with TrackerClient('token', 'org', transport=api.transport()) as client:
            current = client.get_issue('LGS-1', with_comments=False)
            draft = IssueDraft.for_update(current, story_points=5, set_story_points=True)
            result = client.update_issue('LGS-1', draft).to_payload()

        # assert
        assert result['storyPoints'] == 5
        assert json.loads(api.requests[-1].content)['storyPoints'] == 5

    def test_execute_transition__posts_resolution_and_returns_new_status(self) -> None:
        # arrange
        api = FakeTrackerApi()
        api.add_issue('LGS-1', summary='Title', description='Body', issue_type='Backend', status='Open')
        api.add_transition('LGS-1', transition_id='close', display='Закрыть', status='Закрыт', status_key='closed')
        change = IssueStatusChange.parse('Закрыт', 'fixed')

        # act
        with TrackerClient('token', 'org', transport=api.transport()) as client:
            result = client.execute_transition('LGS-1', change, 'close').to_payload()

        # assert
        assert result['status'] == 'Закрыт'
        execute, refetch = api.requests
        assert execute.method == 'POST'
        assert execute.url.path == '/v3/issues/LGS-1/transitions/close/_execute'
        assert json.loads(execute.content) == {'resolution': 'fixed'}
        assert refetch.method == 'GET'
        assert refetch.url.path == '/v3/issues/LGS-1'

    def test_get_issue__unauthorized__raises_tracker_error(self) -> None:
        # arrange
        api = FakeTrackerApi()
        api.status_overrides['/v3/issues/LGS-584'] = 401

        # act / assert
        with (
            TrackerClient('token', 'org', transport=api.transport()) as client,
            pytest.raises(TrackerError, match='401'),
        ):
            client.get_issue('LGS-584')

    def test_from_response__org_not_found__includes_details(self) -> None:
        # arrange
        response = httpx.Response(
            403,
            json={
                'errors': {},
                'errorMessages': ['Organization is not available, not ready or not found'],
                'errorCode': 620345,
            },
        )

        # act
        message = str(TrackerApiError.from_response(response, 'issues/LGS-584'))

        # assert
        assert '403' in message
        assert 'Organization is not available' in message

    def test_get_issue__includes_parent_and_epic_refs(self) -> None:
        # arrange
        api = FakeTrackerApi()
        api.add_issue('DISC-869', summary='Load dictionaries', issue_type='Epic')
        api.add_issue('LGS-1', summary='Parent task', issue_type='Feature')
        api.add_issue(
            'LGS-584',
            summary='Title',
            description='Body',
            issue_type='Backend',
            parent='LGS-1',
            epic='DISC-869',
        )

        # act
        with TrackerClient('token', 'org', transport=api.transport()) as client:
            result = client.get_issue('LGS-584', with_comments=False).to_payload()

        # assert
        assert result['parent'] == {'key': 'LGS-1', 'summary': 'Parent task'}
        assert result['epic'] == {'key': 'DISC-869', 'summary': 'Load dictionaries'}

    def test_list_links__strips_pii_and_maps_relationship(self) -> None:
        # arrange
        api = FakeTrackerApi()
        api.add_issue('DISC-869', summary='Load dictionaries', issue_type='Epic')
        api.add_link(
            'DISC-869',
            relationship='epic',
            direction='outward',
            object_key='LGS-563',
            object_summary='Models',
            outward='Epic for',
            inward='Sub-epic',
        )
        api.add_link(
            'DISC-869',
            relationship='relates',
            direction='outward',
            object_key='LGS-40',
            object_summary='Counterparties',
            status='In Progress',
            outward='relates',
            inward='relates',
        )

        # act
        with TrackerClient('token', 'org', transport=api.transport()) as client:
            key, links = client.list_links('https://tracker.yandex.ru/DISC-869')

        # assert
        assert key.value == 'DISC-869'
        payloads = [link.to_payload() for link in links]
        assert payloads == [
            {
                'relationship': 'epic',
                'label': 'Epic for',
                'direction': 'outward',
                'key': 'LGS-563',
                'summary': 'Models',
                'status': 'Open',
            },
            {
                'relationship': 'relates',
                'label': 'relates',
                'direction': 'outward',
                'key': 'LGS-40',
                'summary': 'Counterparties',
                'status': 'In Progress',
            },
        ]
        dumped = json.dumps(payloads)
        assert 'ivan' not in dumped
        assert 'petr' not in dumped
        assert 'olga' not in dumped
        assert [request.url.path for request in api.requests] == ['/v3/issues/DISC-869/links']

    def test_list_epic_issues__searches_and_paginates(self) -> None:
        # arrange
        api = FakeTrackerApi()
        api.add_issue('DISC-869', summary='Load dictionaries', issue_type='Epic')
        api.add_issue(
            'LGS-563',
            summary='Models',
            issue_type='Backend',
            status='Open',
            epic='DISC-869',
            story_points=5,
        )
        api.add_issue('LGS-40', summary='Counterparties', issue_type='Feature', status='In Progress', epic='DISC-869')

        # act
        with TrackerClient('token', 'org', transport=api.transport()) as client:
            key, issues = client.list_epic_issues('https://tracker.yandex.ru/DISC-869')

        # assert
        assert key.value == 'DISC-869'
        assert [item.to_payload() for item in issues] == [
            {'key': 'LGS-563', 'summary': 'Models', 'type': 'Backend', 'status': 'Open', 'storyPoints': 5},
            {
                'key': 'LGS-40',
                'summary': 'Counterparties',
                'type': 'Feature',
                'status': 'In Progress',
                'storyPoints': None,
            },
        ]
        assert [request.url.path for request in api.requests] == [
            '/v3/issues/_search',
            '/v3/issues/_search',
        ]
        assert json.loads(api.requests[0].content) == {'query': 'epic: "DISC-869"'}
        dumped = json.dumps([item.to_payload() for item in issues])
        assert 'ivan' not in dumped
        assert 'petr' not in dumped

    def test_list_project_epics__searches_and_paginates(self) -> None:
        # arrange
        api = FakeTrackerApi()
        api.add_issue('LGS-1', summary='First epic', issue_type='Epic', project='5787', story_points=8)
        api.add_issue('LGS-2', summary='Second epic', issue_type='Epic', project='5787', status='In Progress')
        api.add_issue('LGS-3', summary='Other project', issue_type='Epic', project='9999')
        api.add_issue('LGS-4', summary='Task in project', issue_type='Backend', project='5787')

        # act
        with TrackerClient('token', 'org', transport=api.transport()) as client:
            project, epics = client.list_project_epics('https://tracker.yandex.ru/pages/projects/5787/')

        # assert
        assert project.value == '5787'
        assert [item.to_payload() for item in epics] == [
            {'key': 'LGS-1', 'summary': 'First epic', 'type': 'Epic', 'status': 'Open', 'storyPoints': 8},
            {
                'key': 'LGS-2',
                'summary': 'Second epic',
                'type': 'Epic',
                'status': 'In Progress',
                'storyPoints': None,
            },
        ]
        assert [request.url.path for request in api.requests] == [
            '/v3/issues/_search',
            '/v3/issues/_search',
        ]
        assert json.loads(api.requests[0].content) == {'filter': {'type': 'epic', 'project': 5787}}
        dumped = json.dumps([item.to_payload() for item in epics])
        assert 'ivan' not in dumped
        assert 'petr' not in dumped

    def test_list_project_epics__by_name__uses_query_language(self) -> None:
        # arrange
        api = FakeTrackerApi()
        api.add_issue(
            'LGS-1',
            summary='Named epic',
            issue_type='Epic',
            extra={'project': {'primary': {'id': '1', 'display': 'Logistics'}}},
        )

        # act
        with TrackerClient('token', 'org', transport=api.transport()) as client:
            project, epics = client.list_project_epics('Logistics')

        # assert
        assert project.value == 'Logistics'
        assert [item.key for item in epics] == ['LGS-1']
        assert json.loads(api.requests[0].content) == {'query': 'Type: Epic "Project": "Logistics"'}

    def test_list_comments__strips_pii(self) -> None:
        # arrange
        api = FakeTrackerApi()
        api.add_issue('LGS-584', summary='Title', description='Body', issue_type='Backend')
        api.add_comment('LGS-584', 'First', '2026-01-01T00:00:00.000+0000')
        api.add_comment('LGS-584', 'Second', '2026-01-02T00:00:00.000+0000', author='olga')

        # act
        with TrackerClient('token', 'org', transport=api.transport()) as client:
            key, comments = client.list_comments('https://tracker.yandex.ru/LGS-584')

        # assert
        assert key.value == 'LGS-584'
        payloads = [comment.to_payload() for comment in comments]
        assert payloads == [
            {
                'id': '1',
                'text': 'First',
                'createdAt': '2026-01-01T00:00:00.000+0000',
                'updatedAt': '2026-01-01T00:00:00.000+0000',
            },
            {
                'id': '2',
                'text': 'Second',
                'createdAt': '2026-01-02T00:00:00.000+0000',
                'updatedAt': '2026-01-02T00:00:00.000+0000',
            },
        ]
        dumped = json.dumps(payloads)
        assert 'ivan' not in dumped
        assert 'olga' not in dumped

    def test_create_comment__posts_text(self) -> None:
        # arrange
        api = FakeTrackerApi()
        api.add_issue('LGS-584', summary='Title', description='Body', issue_type='Backend')
        draft = CommentDraft.parse('Looks good')

        # act
        with TrackerClient('token', 'org', transport=api.transport()) as client:
            result = client.create_comment('LGS-584', draft).to_payload()

        # assert
        assert result == {
            'id': '1',
            'text': 'Looks good',
            'createdAt': '2026-01-03T00:00:00.000+0000',
            'updatedAt': '2026-01-03T00:00:00.000+0000',
        }
        request = api.requests[0]
        assert request.method == 'POST'
        assert request.url.path == '/v3/issues/LGS-584/comments'
        assert json.loads(request.content) == {'text': 'Looks good'}
        dumped = json.dumps(result)
        assert 'ivan' not in dumped

    def test_update_comment__patches_text(self) -> None:
        # arrange
        api = FakeTrackerApi()
        api.add_issue('LGS-584', summary='Title', description='Body', issue_type='Backend')
        api.add_comment('LGS-584', 'First', '2026-01-01T00:00:00.000+0000')
        draft = CommentDraft.parse('Edited')

        # act
        with TrackerClient('token', 'org', transport=api.transport()) as client:
            result = client.update_comment('LGS-584', '1', draft).to_payload()

        # assert
        assert result == {
            'id': '1',
            'text': 'Edited',
            'createdAt': '2026-01-01T00:00:00.000+0000',
            'updatedAt': '2026-01-04T00:00:00.000+0000',
        }
        request = api.requests[0]
        assert request.method == 'PATCH'
        assert request.url.path == '/v3/issues/LGS-584/comments/1'
        assert json.loads(request.content) == {'text': 'Edited'}
        dumped = json.dumps(result)
        assert 'olga' not in dumped
