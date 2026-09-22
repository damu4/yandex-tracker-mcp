from __future__ import annotations

import pytest

from yandex_tracker_mcp.domain.exceptions import TrackerError
from yandex_tracker_mcp.domain.issue import (
    CommentDraft,
    Issue,
    IssueDraft,
    IssueKey,
    IssueLink,
    IssueStatusChange,
    IssueSummary,
    IssueTransition,
    IssueType,
    ProjectId,
)


class TestIssueKey:
    @pytest.mark.parametrize(
        ('value', 'expected'),
        [
            ('LGS-584', 'LGS-584'),
            ('lgs-584', 'LGS-584'),
            ('https://tracker.yandex.ru/LGS-584', 'LGS-584'),
            ('https://tracker.yandex.ru/LGS-584/', 'LGS-584'),
            ('see ticket https://tracker.yandex.ru/LGS-584 please', 'LGS-584'),
        ],
    )
    def test_parse__valid_key_or_url__returns_normalized_key(self, value: str, expected: str) -> None:
        # arrange / act
        result = IssueKey.parse(value)

        # assert
        assert result.value == expected

    def test_parse__garbage__raises_tracker_error(self) -> None:
        # act / assert
        with pytest.raises(TrackerError, match='Could not parse'):
            IssueKey.parse('not a ticket')


class TestProjectId:
    @pytest.mark.parametrize(
        ('value', 'expected'),
        [
            ('5787', '5787'),
            (' 5787 ', '5787'),
            ('https://tracker.yandex.ru/pages/projects/5787/', '5787'),
            ('https://tracker.yandex.ru/pages/projects/5787', '5787'),
            ('https://tracker.yandex.ru/pages/projects/5787/?tab=issues', '5787'),
        ],
    )
    def test_parse__id_or_url__returns_numeric_id(self, value: str, expected: str) -> None:
        # act
        result = ProjectId.parse(value)

        # assert
        assert result.value == expected
        assert result.is_numeric
        assert result.epic_search_query() == 'Type: Epic Project: 5787'

    def test_parse__project_name__keeps_name_in_query(self) -> None:
        # act
        result = ProjectId.parse('Logistics')

        # assert
        assert result.value == 'Logistics'
        assert not result.is_numeric
        assert result.epic_search_query() == 'Type: Epic "Project": "Logistics"'

    def test_parse__empty__raises_tracker_error(self) -> None:
        # act / assert
        with pytest.raises(TrackerError, match='Could not parse a Tracker project'):
            ProjectId.parse('  ')


class TestIssueType:
    @pytest.mark.parametrize('value', ['backend', 'Backend', 'BE', 'бэкенд'])
    def test_parse__backend_alias__normalizes_to_backend(self, value: str) -> None:
        # act
        result = IssueType.parse(value)

        # assert
        assert result.name == 'Backend'
        assert result.is_backend

    def test_parse__custom_type__keeps_name(self) -> None:
        # act
        result = IssueType.parse('Feature')

        # assert
        assert result.name == 'Feature'
        assert not result.is_backend

    def test_parse__task_alias__normalizes_to_zadacha(self) -> None:
        # act
        result = IssueType.parse('задача')

        # assert
        assert result.name == 'Задача'

    def test_parse__frontend_alias__normalizes_to_frontend(self) -> None:
        # act
        result = IssueType.parse('fe')

        # assert
        assert result.name == 'Frontend'

    @pytest.mark.parametrize('value', ['qa', 'QA'])
    def test_parse__qa_alias__normalizes_to_qa(self, value: str) -> None:
        # act
        result = IssueType.parse(value)

        # assert
        assert result.name == 'QA'

    @pytest.mark.parametrize('value', ['ошибка', 'bug', 'error', 'Ошибка'])
    def test_parse__bug_alias__normalizes_to_oshibka(self, value: str) -> None:
        # act
        result = IssueType.parse(value)

        # assert
        assert result.name == 'Ошибка'

    @pytest.mark.parametrize('value', ['автотесты', 'autotest', 'autotests'])
    def test_parse__autotest_alias__normalizes_to_autotesty(self, value: str) -> None:
        # act
        result = IssueType.parse(value)

        # assert
        assert result.name == 'Автотесты'

    def test_parse__empty__raises_tracker_error(self) -> None:
        # act / assert
        with pytest.raises(TrackerError, match='Issue type must not be empty'):
            IssueType.parse('  ')


class TestIssueSummary:
    def test_parse__backend_without_prefix__adds_be_prefix(self) -> None:
        # act
        result = IssueSummary.parse('Fix login', issue_type=IssueType('Backend'))

        # assert
        assert result.value == 'BE: Fix login'

    def test_parse__backend_with_prefix__normalizes_spacing(self) -> None:
        # act
        result = IssueSummary.parse('BE:Fix login', issue_type=IssueType('Backend'))

        # assert
        assert result.value == 'BE: Fix login'

    def test_parse__non_backend__keeps_title(self) -> None:
        # act
        result = IssueSummary.parse('Fix login', issue_type=IssueType('Feature'))

        # assert
        assert result.value == 'Fix login'

    def test_parse__frontend_without_prefix__adds_fe_prefix(self) -> None:
        # act
        result = IssueSummary.parse('Add filters', issue_type=IssueType('Frontend'))

        # assert
        assert result.value == 'FE: Add filters'

    def test_parse__frontend_with_prefix__normalizes_spacing(self) -> None:
        # act
        result = IssueSummary.parse('FE:Add filters', issue_type=IssueType('Frontend'))

        # assert
        assert result.value == 'FE: Add filters'

    def test_parse__qa__does_not_prefix_title(self) -> None:
        # act
        result = IssueSummary.parse('[QA MT] Dictionaries', issue_type=IssueType('QA'))

        # assert
        assert result.value == '[QA MT] Dictionaries'

    def test_parse__strip_backend_prefix__removes_prefix(self) -> None:
        # act
        result = IssueSummary.parse(
            'BE: Fix login',
            issue_type=IssueType('Feature'),
            previous_type=IssueType('Backend'),
        )

        # assert
        assert result.value == 'Fix login'

    def test_parse__strip_frontend_prefix__removes_prefix(self) -> None:
        # act
        result = IssueSummary.parse(
            'FE: Add filters',
            issue_type=IssueType('QA'),
            previous_type=IssueType('Frontend'),
        )

        # assert
        assert result.value == 'Add filters'

    def test_parse__empty__raises_tracker_error(self) -> None:
        # act / assert
        with pytest.raises(TrackerError, match='Issue summary must not be empty'):
            IssueSummary.parse('  ', issue_type=IssueType('Feature'))


class TestIssueDraft:
    def test_for_create__backend__sets_prefix_and_type(self) -> None:
        # act
        draft = IssueDraft.for_create(
            issue_type='backend',
            summary='Add rates',
            description='Details',
        )

        # assert
        assert draft.issue_type.name == 'Backend'
        assert draft.summary.value == 'BE: Add rates'
        assert draft.description == 'Details'
        assert draft.to_tracker_payload(queue='LGS') == {
            'queue': 'LGS',
            'summary': 'BE: Add rates',
            'description': 'Details',
            'type': {'name': 'Backend'},
        }

    def test_for_create__with_epic__adds_has_epic_link(self) -> None:
        # act
        draft = IssueDraft.for_create(
            issue_type='backend',
            summary='Add rates',
            description='Details',
            epic='https://tracker.yandex.ru/LGS-275',
        )

        # assert
        assert draft.epic is not None
        assert draft.epic.value == 'LGS-275'
        assert draft.to_tracker_payload(queue='LGS')['links'] == [
            {'relationship': 'has epic', 'issue': 'LGS-275'},
        ]

    def test_for_create__with_story_points__includes_field(self) -> None:
        # act
        draft = IssueDraft.for_create(
            issue_type='задача',
            summary='Estimate work',
            description='Details',
            story_points=3,
        )

        # assert
        assert draft.issue_type.name == 'Задача'
        assert draft.to_tracker_payload(queue='LGS')['storyPoints'] == 3

    def test_for_create__feature__does_not_prefix_title(self) -> None:
        # act
        draft = IssueDraft.for_create(
            issue_type='Feature',
            summary='Add rates',
            description='Details',
        )

        # assert
        assert draft.summary.value == 'Add rates'
        assert draft.issue_type.name == 'Feature'

    def test_for_create__frontend__sets_prefix_and_type(self) -> None:
        # act
        draft = IssueDraft.for_create(
            issue_type='fe',
            summary='Add filters',
            description='Details',
        )

        # assert
        assert draft.issue_type.name == 'Frontend'
        assert draft.summary.value == 'FE: Add filters'
        assert draft.to_tracker_payload(queue='LGS')['type'] == {'name': 'Frontend'}

    def test_for_create__qa__keeps_title(self) -> None:
        # act
        draft = IssueDraft.for_create(
            issue_type='qa',
            summary='[QA MT] Dictionaries',
            description='Details',
        )

        # assert
        assert draft.issue_type.name == 'QA'
        assert draft.summary.value == '[QA MT] Dictionaries'

    def test_for_update__to_backend__adds_prefix_and_type(self) -> None:
        # arrange
        current = Issue(
            key='LGS-1',
            summary='Add rates',
            description='Old',
            issue_type=IssueType('Feature'),
        )

        # act
        draft = IssueDraft.for_update(current, issue_type='backend')

        # assert
        assert draft.issue_type.name == 'Backend'
        assert draft.summary.value == 'BE: Add rates'
        assert draft.description == 'Old'

    def test_for_update__from_backend__strips_prefix(self) -> None:
        # arrange
        current = Issue(
            key='LGS-1',
            summary='BE: Add rates',
            description='Old',
            issue_type=IssueType('Backend'),
        )

        # act
        draft = IssueDraft.for_update(current, issue_type='Feature')

        # assert
        assert draft.issue_type.name == 'Feature'
        assert draft.summary.value == 'Add rates'

    def test_for_update__backend_to_frontend__swaps_prefix(self) -> None:
        # arrange
        current = Issue(
            key='LGS-1',
            summary='BE: Add rates',
            description='Old',
            issue_type=IssueType('Backend'),
        )

        # act
        draft = IssueDraft.for_update(current, issue_type='frontend')

        # assert
        assert draft.issue_type.name == 'Frontend'
        assert draft.summary.value == 'FE: Add rates'

    def test_for_update__from_frontend__strips_prefix(self) -> None:
        # arrange
        current = Issue(
            key='LGS-1',
            summary='FE: Add filters',
            description='Old',
            issue_type=IssueType('Frontend'),
        )

        # act
        draft = IssueDraft.for_update(current, issue_type='QA')

        # assert
        assert draft.issue_type.name == 'QA'
        assert draft.summary.value == 'Add filters'

    def test_for_update__backend_new_title__keeps_prefix(self) -> None:
        # arrange
        current = Issue(
            key='LGS-1',
            summary='BE: Old title',
            description='Old',
            issue_type=IssueType('Backend'),
        )

        # act
        draft = IssueDraft.for_update(current, summary='New title')

        # assert
        assert draft.summary.value == 'BE: New title'
        assert draft.issue_type.name == 'Backend'

    def test_for_update__story_points_only__keeps_rest(self) -> None:
        # arrange
        current = Issue(
            key='LGS-1',
            summary='Title',
            description='Body',
            issue_type=IssueType('Задача'),
            story_points=1,
        )

        # act
        draft = IssueDraft.for_update(current, story_points=5, set_story_points=True)

        # assert
        assert draft.story_points == 5
        assert draft.to_tracker_payload()['storyPoints'] == 5
        assert draft.issue_type.name == 'Задача'

    def test_for_update__no_fields__raises_tracker_error(self) -> None:
        # arrange
        current = Issue(
            key='LGS-1',
            summary='Title',
            description='Body',
            issue_type=IssueType('Feature'),
        )

        # act / assert
        with pytest.raises(TrackerError, match='At least one'):
            IssueDraft.for_update(current)


class TestIssue:
    def test_from_tracker__keeps_whitelist_only(self) -> None:
        # arrange
        raw = {
            'key': 'LGS-584',
            'summary': 'Fix login',
            'description': 'Details here',
            'type': {'display': 'Backend', 'key': 'backend', 'name': 'Backend'},
            'status': {'id': '3', 'key': 'closed', 'display': 'Закрыт'},
            'assignee': {'display': 'Ivan', 'login': 'ivan'},
            'createdBy': {'display': 'Petr', 'login': 'petr'},
            'updatedBy': {'display': 'Olga', 'login': 'olga'},
            'followers': [{'login': 'secret'}],
            'parent': {'key': 'LGS-1', 'display': 'Parent task', 'assignee': {'login': 'ivan'}},
            'epic': {'key': 'DISC-869', 'display': 'Load dictionaries', 'assignee': {'login': 'petr'}},
            'storyPoints': 8,
        }
        comments = [
            {
                'id': 626,
                'longId': '626',
                'text': 'Looks good',
                'createdAt': '2026-01-02T03:04:05.000+0000',
                'updatedAt': '2026-01-02T04:00:00.000+0000',
                'createdBy': {'display': 'Ivan', 'login': 'ivan'},
                'updatedBy': {'display': 'Ivan', 'login': 'ivan'},
            },
        ]

        # act
        result = Issue.from_tracker(raw, comments).to_payload()

        # assert
        assert result == {
            'key': 'LGS-584',
            'summary': 'Fix login',
            'description': 'Details here',
            'type': 'Backend',
            'status': 'Закрыт',
            'storyPoints': 8,
            'parent': {'key': 'LGS-1', 'summary': 'Parent task'},
            'epic': {'key': 'DISC-869', 'summary': 'Load dictionaries'},
            'comments': [
                {
                    'id': '626',
                    'text': 'Looks good',
                    'createdAt': '2026-01-02T03:04:05.000+0000',
                    'updatedAt': '2026-01-02T04:00:00.000+0000',
                },
            ],
        }
        dumped = str(result)
        assert 'ivan' not in dumped
        assert 'Petr' not in dumped
        assert 'Olga' not in dumped
        assert 'assignee' not in dumped
        assert 'createdBy' not in dumped
        assert 'closed' not in dumped


class TestIssueStatusChange:
    def test_parse__strips_status_and_resolution(self) -> None:
        # act
        change = IssueStatusChange.parse('  В работе  ', '  fixed  ')

        # assert
        assert change.status == 'В работе'
        assert change.resolution == 'fixed'

    def test_parse__empty_status__raises_tracker_error(self) -> None:
        # act / assert
        with pytest.raises(TrackerError, match='Issue status must not be empty'):
            IssueStatusChange.parse('  ')

    def test_parse__empty_resolution__raises_tracker_error(self) -> None:
        # act / assert
        with pytest.raises(TrackerError, match='Resolution must not be empty'):
            IssueStatusChange.parse('Закрыт', '  ')

    def test_match__accepts_status_name_key_and_transition_id(self) -> None:
        # arrange
        transition = IssueTransition.from_tracker(
            {
                'id': 'start_progress',
                'display': 'В работу',
                'to': {'key': 'inProgress', 'display': 'В работе'},
            },
        )
        change = IssueStatusChange.parse('inProgress')

        # act
        matched = change.match((transition,))

        # assert
        assert matched == transition
        assert transition.matches('В работе')
        assert transition.matches('start_progress')
        assert transition.label == 'В работе (start_progress)'

    def test_matches_current__same_status_key(self) -> None:
        # arrange
        issue = Issue(
            key='KRA-417',
            summary='Title',
            description='',
            issue_type=IssueType('Backend'),
            status='В работе',
            status_key='inProgress',
        )

        # act
        same = IssueStatusChange.parse('inProgress').matches_current(issue)

        # assert
        assert same is True


class TestCommentDraft:
    def test_parse__strips_text(self) -> None:
        # act
        draft = CommentDraft.parse('  Looks good  ')

        # assert
        assert draft.text == 'Looks good'
        assert draft.to_tracker_payload() == {'text': 'Looks good'}

    def test_parse__empty__raises_tracker_error(self) -> None:
        # act / assert
        with pytest.raises(TrackerError, match='Comment text must not be empty'):
            CommentDraft.parse('  ')

    def test_parse_id__empty__raises_tracker_error(self) -> None:
        # act / assert
        with pytest.raises(TrackerError, match='Comment id must not be empty'):
            CommentDraft.parse_id('  ')


class TestIssueLink:
    def test_from_tracker__keeps_whitelist_only(self) -> None:
        # arrange
        raw = {
            'id': 47,
            'type': {
                'id': 'epic',
                'inward': 'Sub-epic',
                'outward': 'Epic for',
            },
            'direction': 'outward',
            'object': {
                'key': 'LGS-563',
                'display': 'Models',
                'assignee': {'login': 'ivan'},
            },
            'status': {'id': '1', 'key': 'open', 'display': 'Open'},
            'assignee': {'login': 'ivan', 'display': 'Ivan'},
            'createdBy': {'login': 'petr', 'display': 'Petr'},
            'updatedBy': {'login': 'olga', 'display': 'Olga'},
        }

        # act
        result = IssueLink.from_tracker(raw).to_payload()

        # assert
        assert result == {
            'relationship': 'epic',
            'label': 'Epic for',
            'direction': 'outward',
            'key': 'LGS-563',
            'summary': 'Models',
            'status': 'Open',
        }
        dumped = str(result)
        assert 'ivan' not in dumped
        assert 'petr' not in dumped
        assert 'olga' not in dumped
