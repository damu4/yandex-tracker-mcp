from __future__ import annotations

import pytest

from tests.fakes import FakeTrackerApi
from yandex_tracker_mcp.adapters.tracker import TrackerClient
from yandex_tracker_mcp.application.issue_service import IssueService
from yandex_tracker_mcp.domain.exceptions import TrackerError


class TestIssueService:
    def test_create_issue__backend__applies_prefix_and_type(self) -> None:
        # arrange
        api = FakeTrackerApi()

        # act
        with TrackerClient('token', 'org', transport=api.transport()) as client:
            result = IssueService(client, default_queue='LGS').create_issue(
                issue_type='backend',
                summary='Add rates',
                description='Body',
            )

        # assert
        assert result['key'] == 'LGS-1'
        assert result['summary'] == 'BE: Add rates'
        assert result['type'] == 'Backend'
        assert result['description'] == 'Body'
        assert result['comments'] == []

    def test_create_issue__frontend__applies_prefix_and_type(self) -> None:
        # arrange
        api = FakeTrackerApi()

        # act
        with TrackerClient('token', 'org', transport=api.transport()) as client:
            result = IssueService(client, default_queue='LGS').create_issue(
                issue_type='fe',
                summary='Add filters',
                description='Body',
            )

        # assert
        assert result['summary'] == 'FE: Add filters'
        assert result['type'] == 'Frontend'

    def test_create_issue__with_epic__returns_epic_ref(self) -> None:
        # arrange
        api = FakeTrackerApi()
        api.add_issue('LGS-275', summary='Calculator dictionaries', issue_type='Epic')

        # act
        with TrackerClient('token', 'org', transport=api.transport()) as client:
            result = IssueService(client, default_queue='LGS').create_issue(
                issue_type='backend',
                summary='Local params',
                description='Body',
                epic='LGS-275',
            )

        # assert
        assert result['epic'] == {'key': 'LGS-275', 'summary': 'Calculator dictionaries'}

    def test_link_issue__attaches_epic(self) -> None:
        # arrange
        api = FakeTrackerApi()
        api.add_issue('LGS-275', summary='Calculator dictionaries', issue_type='Epic')
        api.add_issue('LGS-610', summary='BE: Local params', issue_type='Backend')

        # act
        with TrackerClient('token', 'org', transport=api.transport()) as client:
            result = IssueService(client, default_queue='LGS').link_issue('LGS-610', target='LGS-275')

        # assert
        assert result['key'] == 'LGS-610'
        assert result['epic'] == {'key': 'LGS-275', 'summary': 'Calculator dictionaries'}

    def test_create_issue__custom_queue__uses_argument(self) -> None:
        # arrange
        api = FakeTrackerApi()

        # act
        with TrackerClient('token', 'org', transport=api.transport()) as client:
            result = IssueService(client, default_queue='LGS').create_issue(
                issue_type='Feature',
                summary='Title',
                description='Body',
                queue='DISC',
            )

        # assert
        assert result['key'] == 'DISC-1'
        assert result['summary'] == 'Title'
        assert result['type'] == 'Feature'

    def test_create_issue__with_story_points__returns_points(self) -> None:
        # arrange
        api = FakeTrackerApi()

        # act
        with TrackerClient('token', 'org', transport=api.transport()) as client:
            result = IssueService(client, default_queue='LGS').create_issue(
                issue_type='задача',
                summary='Title',
                description='Body',
                story_points=2,
            )

        # assert
        assert result['type'] == 'Задача'
        assert result['storyPoints'] == 2

    def test_update_issue__story_points_and_type(self) -> None:
        # arrange
        api = FakeTrackerApi()
        api.add_issue('LGS-10', summary='Title', description='Body', issue_type='Backend', story_points=1)

        # act
        with TrackerClient('token', 'org', transport=api.transport()) as client:
            result = IssueService(client, default_queue='LGS').update_issue(
                'LGS-10',
                issue_type='задача',
                story_points=8,
                set_story_points=True,
            )

        # assert
        assert result['type'] == 'Задача'
        assert result['storyPoints'] == 8
        assert result['summary'] == 'Title'

    def test_update_issue_status__executes_matching_transition(self) -> None:
        # arrange
        api = FakeTrackerApi()
        api.add_issue('LGS-10', summary='Title', description='Body', issue_type='Backend', status='Open')
        api.add_transition(
            'LGS-10',
            transition_id='start_progress',
            display='В работу',
            status='В работе',
            status_key='inProgress',
        )

        # act
        with TrackerClient('token', 'org', transport=api.transport()) as client:
            result = IssueService(client, default_queue='LGS').update_issue_status('LGS-10', 'inProgress')

        # assert
        assert result['status'] == 'В работе'
        assert api.requests[-1].url.path == '/v3/issues/LGS-10/transitions/start_progress/_execute'

    def test_update_issue_status__already_current__does_not_execute(self) -> None:
        # arrange
        api = FakeTrackerApi()
        api.add_issue('LGS-10', summary='Title', description='Body', issue_type='Backend', status='Open')
        api.add_transition('LGS-10', transition_id='close', display='Закрыть', status='Закрыт', status_key='closed')

        # act
        with TrackerClient('token', 'org', transport=api.transport()) as client:
            result = IssueService(client, default_queue='LGS').update_issue_status('LGS-10', 'open')

        # assert
        assert result['status'] == 'Open'
        assert [request.method for request in api.requests] == ['GET']

    def test_update_issue_status__unavailable__raises_tracker_error(self) -> None:
        # arrange
        api = FakeTrackerApi()
        api.add_issue('LGS-10', summary='Title', description='Body', issue_type='Backend', status='Open')
        api.add_transition('LGS-10', transition_id='close', display='Закрыть', status='Закрыт', status_key='closed')

        # act / assert
        with (
            TrackerClient('token', 'org', transport=api.transport()) as client,
            pytest.raises(TrackerError, match=r'Available: Закрыт \(close\)'),
        ):
            IssueService(client, default_queue='LGS').update_issue_status('LGS-10', 'В работе')

    def test_update_issue__change_type_to_backend__rewrites_title_and_type(self) -> None:
        # arrange
        api = FakeTrackerApi()
        api.add_issue('LGS-10', summary='Add rates', description='Body', issue_type='Feature')

        # act
        with TrackerClient('token', 'org', transport=api.transport()) as client:
            result = IssueService(client, default_queue='LGS').update_issue(
                'LGS-10',
                issue_type='backend',
            )

        # assert
        assert result['summary'] == 'BE: Add rates'
        assert result['type'] == 'Backend'
        assert result['description'] == 'Body'

    def test_update_issue__change_type_from_backend__strips_prefix(self) -> None:
        # arrange
        api = FakeTrackerApi()
        api.add_issue('LGS-10', summary='BE: Add rates', description='Body', issue_type='Backend')

        # act
        with TrackerClient('token', 'org', transport=api.transport()) as client:
            result = IssueService(client, default_queue='LGS').update_issue(
                'LGS-10',
                issue_type='Feature',
                summary='Add rates UI',
            )

        # assert
        assert result['summary'] == 'Add rates UI'
        assert result['type'] == 'Feature'

    def test_update_issue__change_type_from_frontend__strips_prefix(self) -> None:
        # arrange
        api = FakeTrackerApi()
        api.add_issue('LGS-10', summary='FE: Add filters', description='Body', issue_type='Frontend')

        # act
        with TrackerClient('token', 'org', transport=api.transport()) as client:
            result = IssueService(client, default_queue='LGS').update_issue(
                'LGS-10',
                issue_type='qa',
            )

        # assert
        assert result['summary'] == 'Add filters'
        assert result['type'] == 'QA'

    def test_update_issue__empty_fields__raises_tracker_error(self) -> None:
        # arrange
        api = FakeTrackerApi()
        api.add_issue('LGS-10', summary='Title', description='Body', issue_type='Feature')

        # act / assert
        with (
            TrackerClient('token', 'org', transport=api.transport()) as client,
            pytest.raises(TrackerError, match='At least one'),
        ):
            IssueService(client, default_queue='LGS').update_issue('LGS-10')

    def test_get_epic_issues__returns_epic_children(self) -> None:
        # arrange
        api = FakeTrackerApi()
        api.add_issue('DISC-869', summary='Load dictionaries', issue_type='Epic')
        api.add_issue('LGS-563', summary='Models', issue_type='Backend', epic='DISC-869')

        # act
        with TrackerClient('token', 'org', transport=api.transport()) as client:
            result = IssueService(client, default_queue='LGS').get_epic_issues(
                'https://tracker.yandex.ru/DISC-869',
            )

        # assert
        assert result == {
            'epic': 'DISC-869',
            'issues': [
                {
                    'key': 'LGS-563',
                    'summary': 'Models',
                    'type': 'Backend',
                    'status': 'Open',
                    'storyPoints': None,
                },
            ],
        }

    def test_get_project_epics__returns_project_epics(self) -> None:
        # arrange
        api = FakeTrackerApi()
        api.add_issue('LGS-1', summary='First epic', issue_type='Epic', project='5787')
        api.add_issue('LGS-2', summary='Other project', issue_type='Epic', project='9999')

        # act
        with TrackerClient('token', 'org', transport=api.transport()) as client:
            result = IssueService(client, default_queue='LGS').get_project_epics('5787')

        # assert
        assert result == {
            'project': '5787',
            'epics': [
                {
                    'key': 'LGS-1',
                    'summary': 'First epic',
                    'type': 'Epic',
                    'status': 'Open',
                    'storyPoints': None,
                },
            ],
        }

    def test_get_issue_links__returns_sanitized_links(self) -> None:
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

        # act
        with TrackerClient('token', 'org', transport=api.transport()) as client:
            result = IssueService(client, default_queue='LGS').get_issue_links('DISC-869')

        # assert
        assert result == {
            'key': 'DISC-869',
            'links': [
                {
                    'relationship': 'epic',
                    'label': 'Epic for',
                    'direction': 'outward',
                    'key': 'LGS-563',
                    'summary': 'Models',
                    'status': 'Open',
                },
            ],
        }

    def test_get_comments__returns_whitelist(self) -> None:
        # arrange
        api = FakeTrackerApi()
        api.add_issue('LGS-584', summary='Title', description='Body', issue_type='Backend')
        api.add_comment('LGS-584', 'First', '2026-01-01T00:00:00.000+0000')

        # act
        with TrackerClient('token', 'org', transport=api.transport()) as client:
            result = IssueService(client, default_queue='LGS').get_comments('LGS-584')

        # assert
        assert result == {
            'key': 'LGS-584',
            'comments': [
                {
                    'id': '1',
                    'text': 'First',
                    'createdAt': '2026-01-01T00:00:00.000+0000',
                    'updatedAt': '2026-01-01T00:00:00.000+0000',
                },
            ],
        }

    def test_create_comment__returns_comment(self) -> None:
        # arrange
        api = FakeTrackerApi()
        api.add_issue('LGS-584', summary='Title', description='Body', issue_type='Backend')

        # act
        with TrackerClient('token', 'org', transport=api.transport()) as client:
            result = IssueService(client, default_queue='LGS').create_comment('LGS-584', 'Looks good')

        # assert
        assert result == {
            'id': '1',
            'text': 'Looks good',
            'createdAt': '2026-01-03T00:00:00.000+0000',
            'updatedAt': '2026-01-03T00:00:00.000+0000',
        }

    def test_update_comment__returns_comment(self) -> None:
        # arrange
        api = FakeTrackerApi()
        api.add_issue('LGS-584', summary='Title', description='Body', issue_type='Backend')
        api.add_comment('LGS-584', 'First', '2026-01-01T00:00:00.000+0000')

        # act
        with TrackerClient('token', 'org', transport=api.transport()) as client:
            result = IssueService(client, default_queue='LGS').update_comment('LGS-584', '1', 'Edited')

        # assert
        assert result == {
            'id': '1',
            'text': 'Edited',
            'createdAt': '2026-01-01T00:00:00.000+0000',
            'updatedAt': '2026-01-04T00:00:00.000+0000',
        }

    def test_create_comment__empty_text__raises_tracker_error(self) -> None:
        # arrange
        api = FakeTrackerApi()
        api.add_issue('LGS-584', summary='Title', description='Body', issue_type='Backend')

        # act / assert
        with (
            TrackerClient('token', 'org', transport=api.transport()) as client,
            pytest.raises(TrackerError, match='Comment text must not be empty'),
        ):
            IssueService(client, default_queue='LGS').create_comment('LGS-584', '  ')
