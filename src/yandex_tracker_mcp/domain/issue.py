from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, ClassVar

from yandex_tracker_mcp.domain.exceptions import TrackerError


class TrackerRef:
    @staticmethod
    def name(value: Any) -> str:
        if isinstance(value, dict):
            return str(value.get('display') or value.get('name') or value.get('key') or '')
        return str(value or '')


@dataclass(frozen=True)
class IssueKey:
    PATTERN: ClassVar[re.Pattern[str]] = re.compile(r'\b([A-Za-z][A-Za-z0-9]+-\d+)\b')

    value: str

    @classmethod
    def parse(cls, issue: str) -> IssueKey:
        match = cls.PATTERN.search(issue.strip())
        if not match:
            raise TrackerError(
                'Could not parse a Tracker issue key. '
                'Pass a key like LGS-584 or a URL like https://tracker.yandex.ru/LGS-584.',
                code='INVALID_ISSUE_KEY',
            )
        queue, number = match.group(1).rsplit('-', 1)
        return cls(f'{queue.upper()}-{number}')

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class ProjectId:
    URL_PATTERN: ClassVar[re.Pattern[str]] = re.compile(r'/projects/(\d+)')
    ID_PATTERN: ClassVar[re.Pattern[str]] = re.compile(r'^\d+$')

    value: str

    @classmethod
    def parse(cls, project: str) -> ProjectId:
        stripped = project.strip()
        url_match = cls.URL_PATTERN.search(stripped)
        if url_match:
            return cls(url_match.group(1))
        if cls.ID_PATTERN.match(stripped):
            return cls(stripped)
        if stripped:
            return cls(stripped)
        raise TrackerError(
            'Could not parse a Tracker project. '
            'Pass an ID like 5787 or a URL like https://tracker.yandex.ru/pages/projects/5787/.',
            code='INVALID_PROJECT',
        )

    @property
    def is_numeric(self) -> bool:
        return self.value.isdigit()

    def epic_search_query(self) -> str:
        if self.is_numeric:
            return f'Type: Epic Project: {self.value}'
        escaped = self.value.replace('"', r'\"')
        return f'Type: Epic "Project": "{escaped}"'

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class IssueType:
    BACKEND_NAME: ClassVar[str] = 'Backend'
    ALIASES: ClassVar[dict[str, str]] = {
        'backend': 'Backend',
        'be': 'Backend',
        'бэкенд': 'Backend',
        'frontend': 'Frontend',
        'fe': 'Frontend',
        'фронтенд': 'Frontend',
        'задача': 'Задача',
        'task': 'Задача',
        'qa': 'QA',
        'ошибка': 'Ошибка',
        'bug': 'Ошибка',
        'error': 'Ошибка',
        'автотесты': 'Автотесты',
        'autotest': 'Автотесты',
        'autotests': 'Автотесты',
    }
    TITLE_PREFIXES: ClassVar[dict[str, str]] = {
        'backend': 'BE:',
        'frontend': 'FE:',
    }

    name: str

    @classmethod
    def parse(cls, value: str) -> IssueType:
        stripped = value.strip()
        if not stripped:
            raise TrackerError('Issue type must not be empty.', code='INVALID_ISSUE_TYPE')
        return cls(cls.ALIASES.get(stripped.casefold(), stripped))

    @classmethod
    def from_tracker(cls, raw: Any) -> IssueType:
        return cls(TrackerRef.name(raw).strip())

    @property
    def is_backend(self) -> bool:
        return self.name.casefold() == self.BACKEND_NAME.casefold()

    @property
    def title_prefix(self) -> str | None:
        return self.TITLE_PREFIXES.get(self.name.casefold())


def parse_story_points(value: Any) -> int | float | None:
    if value is None or value == '':
        return None
    if isinstance(value, bool):
        raise TrackerError('Story points must be a number.', code='INVALID_STORY_POINTS')
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise TrackerError('Story points must be a number.', code='INVALID_STORY_POINTS') from exc
    if number < 0:
        raise TrackerError('Story points must not be negative.', code='INVALID_STORY_POINTS')
    if number.is_integer():
        return int(number)
    return number


@dataclass(frozen=True)
class IssueSummary:
    value: str

    @classmethod
    def parse(
        cls,
        value: str,
        *,
        issue_type: IssueType,
        previous_type: IssueType | None = None,
    ) -> IssueSummary:
        text = value.strip()
        new_prefix = issue_type.title_prefix
        old_prefix = previous_type.title_prefix if previous_type is not None else None
        if old_prefix and old_prefix.casefold() != (new_prefix or '').casefold():
            text = cls._without_prefix(text, old_prefix)
        if new_prefix:
            text = cls._with_prefix(text, new_prefix)
        if not text or (new_prefix and text.casefold() == new_prefix.casefold()):
            raise TrackerError('Issue summary must not be empty.', code='INVALID_ISSUE_SUMMARY')
        return cls(text)

    @classmethod
    def _with_prefix(cls, text: str, prefix: str) -> str:
        rest = text[len(prefix) :].strip() if cls._has_prefix(text, prefix) else text
        return f'{prefix} {rest}' if rest else prefix

    @classmethod
    def _without_prefix(cls, text: str, prefix: str) -> str:
        if cls._has_prefix(text, prefix):
            return text[len(prefix) :].strip()
        return text

    @classmethod
    def _has_prefix(cls, text: str, prefix: str) -> bool:
        return text.casefold().startswith(prefix.casefold())


@dataclass(frozen=True)
class IssueComment:
    id: str
    text: str
    created_at: str
    updated_at: str = ''

    @classmethod
    def from_tracker(cls, raw: dict[str, Any]) -> IssueComment:
        return cls(
            id=str(raw.get('id') or raw.get('longId') or ''),
            text=str(raw.get('text') or ''),
            created_at=str(raw.get('createdAt') or ''),
            updated_at=str(raw.get('updatedAt') or ''),
        )

    def to_payload(self) -> dict[str, str]:
        return {
            'id': self.id,
            'text': self.text,
            'createdAt': self.created_at,
            'updatedAt': self.updated_at,
        }


@dataclass(frozen=True)
class CommentDraft:
    text: str

    @classmethod
    def parse(cls, text: str) -> CommentDraft:
        stripped = text.strip()
        if not stripped:
            raise TrackerError('Comment text must not be empty.', code='INVALID_COMMENT')
        return cls(stripped)

    @staticmethod
    def parse_id(comment_id: str | int) -> str:
        parsed = str(comment_id).strip()
        if not parsed:
            raise TrackerError('Comment id must not be empty.', code='INVALID_COMMENT_ID')
        return parsed

    def to_tracker_payload(self) -> dict[str, str]:
        return {'text': self.text}


@dataclass(frozen=True)
class IssueRef:
    key: str
    summary: str

    @classmethod
    def from_tracker(cls, raw: Any) -> IssueRef | None:
        if not isinstance(raw, dict):
            return None
        key = str(raw.get('key') or '')
        if not key:
            return None
        return cls(key=key, summary=str(raw.get('display') or raw.get('summary') or ''))

    def to_payload(self) -> dict[str, str]:
        return {
            'key': self.key,
            'summary': self.summary,
        }


@dataclass(frozen=True)
class IssueListItem:
    key: str
    summary: str
    issue_type: IssueType
    status: str
    story_points: int | float | None = None

    @classmethod
    def from_tracker(cls, raw: dict[str, Any]) -> IssueListItem:
        return cls(
            key=str(raw.get('key') or ''),
            summary=str(raw.get('summary') or raw.get('display') or ''),
            issue_type=IssueType.from_tracker(raw.get('type')),
            status=TrackerRef.name(raw.get('status')),
            story_points=parse_story_points(raw.get('storyPoints')),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            'key': self.key,
            'summary': self.summary,
            'type': self.issue_type.name,
            'status': self.status,
            'storyPoints': self.story_points,
        }


@dataclass(frozen=True)
class IssueLink:
    HAS_EPIC: ClassVar[str] = 'has epic'
    relationship: str
    label: str
    direction: str
    key: str
    summary: str
    status: str

    @classmethod
    def from_tracker(cls, raw: dict[str, Any]) -> IssueLink:
        link_type = raw.get('type') if isinstance(raw.get('type'), dict) else {}
        direction = str(raw.get('direction') or '')
        label_key = 'outward' if direction == 'outward' else 'inward'
        obj = raw.get('object') if isinstance(raw.get('object'), dict) else {}
        return cls(
            relationship=str(link_type.get('id') or ''),
            label=str(link_type.get(label_key) or ''),
            direction=direction,
            key=str(obj.get('key') or ''),
            summary=str(obj.get('display') or obj.get('summary') or ''),
            status=TrackerRef.name(raw.get('status')),
        )

    def to_payload(self) -> dict[str, str]:
        return {
            'relationship': self.relationship,
            'label': self.label,
            'direction': self.direction,
            'key': self.key,
            'summary': self.summary,
            'status': self.status,
        }


@dataclass(frozen=True)
class Issue:
    key: str
    summary: str
    description: str
    issue_type: IssueType
    comments: tuple[IssueComment, ...] = ()
    parent: IssueRef | None = None
    epic: IssueRef | None = None
    story_points: int | float | None = None

    @classmethod
    def from_tracker(cls, raw: dict[str, Any], comments: list[dict[str, Any]] | None = None) -> Issue:
        return cls(
            key=str(raw.get('key') or ''),
            summary=str(raw.get('summary') or ''),
            description=str(raw.get('description') or ''),
            issue_type=IssueType.from_tracker(raw.get('type')),
            comments=tuple(IssueComment.from_tracker(item) for item in comments or []),
            parent=IssueRef.from_tracker(raw.get('parent')),
            epic=IssueRef.from_tracker(raw.get('epic')),
            story_points=parse_story_points(raw.get('storyPoints')),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            'key': self.key,
            'summary': self.summary,
            'description': self.description,
            'type': self.issue_type.name,
            'storyPoints': self.story_points,
            'parent': self.parent.to_payload() if self.parent else None,
            'epic': self.epic.to_payload() if self.epic else None,
            'comments': [comment.to_payload() for comment in self.comments],
        }


@dataclass(frozen=True)
class IssueDraft:
    issue_type: IssueType
    summary: IssueSummary
    description: str
    epic: IssueKey | None = None
    story_points: int | float | None = None
    set_story_points: bool = False

    @classmethod
    def for_create(
        cls,
        *,
        issue_type: str,
        summary: str,
        description: str,
        epic: str | None = None,
        story_points: Any = None,
    ) -> IssueDraft:
        parsed_type = IssueType.parse(issue_type)
        parsed_points = parse_story_points(story_points)
        return cls(
            issue_type=parsed_type,
            summary=IssueSummary.parse(summary, issue_type=parsed_type),
            description=description,
            epic=IssueKey.parse(epic) if epic else None,
            story_points=parsed_points,
            set_story_points=parsed_points is not None,
        )

    @classmethod
    def for_update(
        cls,
        current: Issue,
        *,
        issue_type: str | None = None,
        summary: str | None = None,
        description: str | None = None,
        story_points: Any = None,
        set_story_points: bool = False,
    ) -> IssueDraft:
        if issue_type is None and summary is None and description is None and not set_story_points:
            raise TrackerError(
                'At least one of issue_type, summary, description, story_points must be provided.',
                code='EMPTY_ISSUE_UPDATE',
            )
        parsed_type = IssueType.parse(issue_type) if issue_type is not None else current.issue_type
        if issue_type is None and not parsed_type.name:
            raise TrackerError(
                'Current issue has no type; pass issue_type to update the issue.',
                code='MISSING_ISSUE_TYPE',
            )
        return cls(
            issue_type=parsed_type,
            summary=IssueSummary.parse(
                current.summary if summary is None else summary,
                issue_type=parsed_type,
                previous_type=current.issue_type,
            ),
            description=current.description if description is None else description,
            story_points=parse_story_points(story_points) if set_story_points else current.story_points,
            set_story_points=set_story_points,
        )

    def to_tracker_payload(self, *, queue: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            'summary': self.summary.value,
            'description': self.description,
            'type': {'name': self.issue_type.name},
        }
        if queue is not None:
            payload['queue'] = queue
        if self.epic is not None:
            payload['links'] = [{'relationship': 'has epic', 'issue': self.epic.value}]
        if self.set_story_points:
            payload['storyPoints'] = self.story_points
        return payload
