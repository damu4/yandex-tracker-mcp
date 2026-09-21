# Yandex Tracker MCP

MCP-сервер читает, создаёт и обновляет задачи Yandex Tracker, оставляет и правит комментарии, а также отдаёт состав эпика, эпики проекта и связи задачи. В ответ уходят только ключ, тип, Story Points, заголовок, описание, ссылки parent/epic, комментарии (id, текст, даты) и связи без персональных данных. Исполнитель, авторы и другие персональные поля не возвращаются.

## Перенос на другой компьютер

Код переносится через git (предпочтительно) или копированием репозитория **без** `.venv` и `.env`. Виртуальное окружение привязано к машине; токен Tracker нельзя класть в git.

На новой машине нужны:

1. [uv](https://docs.astral.sh/uv/getting-started/installation/) в `PATH` (Cursor тоже должен его видеть)
2. Python 3.13 — `uv` поставит сам: `uv python install 3.13`
3. Свой `YANDEX_TRACKER_TOKEN` и `YANDEX_TRACKER_ORG_ID`

```bash
git clone https://github.com/damu4/yandex-tracker-mcp.git
cd yandex-tracker-mcp
cp .env.example .env
uv python install 3.13
uv sync --group dev
```

Заполните `.env`. Затем откройте эту папку в Cursor: проектный `.cursor/mcp.json` уже указывает на `${workspaceFolder}`.

Если MCP нужен **во всех** чатах Cursor, а не только в этом репозитории, добавьте в `~/.cursor/mcp.json` тот же запуск с каталогом клона. Удобно класть репозиторий в домашнюю папку и писать `${userHome}/yandex_tracker_mcp`:

```json
{
  "mcpServers": {
    "yandex-tracker": {
      "command": "uv",
      "args": ["run", "--directory", "${userHome}/yandex_tracker_mcp", "python", "-m", "yandex_tracker_mcp"],
      "env": {
        "PYTHONUNBUFFERED": "1",
        "TRACKER_MCP_SCHEMA": "2"
      }
    }
  }
}
```

После сохранения конфига перезапустите MCP в Cursor. Секреты читаются из `.env` в корне репозитория, дублировать их в `mcp.json` не нужно.

Если Cursor не находит `uv` (часто у GUI-приложений другой `PATH`), укажите полный путь, например `${userHome}/.local/bin/uv`.

## Настройка

Скопируйте переменные из `.env.example`:

```bash
cp .env.example .env
```

Заполните `YANDEX_TRACKER_TOKEN` и `YANDEX_TRACKER_ORG_ID` (те же имена, что в репозитории staff). Очередь по умолчанию задаётся `YANDEX_TRACKER_QUEUE` (пример: `KRA`).

Если Tracker отвечает `403 Organization is not available`, обновите токен в `.env` и проверьте org ID в Tracker: **Администрирование → Организации → ID**. IAM-токены (`t1.…`) быстро протухают.

Создайте окружение Python 3.13 через uv и установите пакет:

```bash
uv sync --group dev
```

Проверки:

```bash
uv run pytest
uv run ruff check src tests
uv run ruff format --check src tests
```

## Что не класть в git

Не коммитить:

- секреты: `.env`
- окружение: `.venv/`, `.virtualenv-cache/`
- IDE: `.idea/`, `*.iml`
- кэши: `__pycache__/`, `*.py[cod]`, `.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`, `.coverage`, `htmlcov/`
- сборка: `build/`, `dist/`, `*.egg-info/`
- ОС: `.DS_Store`, `Thumbs.db`

Коммитить: `src/`, `tests/`, `pyproject.toml`, `uv.lock`, `.python-version`, `.env.example`, `.cursor/mcp.json`, `.pre-commit-config.yaml`, `.github/workflows/`, README, `.gitignore`.

`.cursor/mcp.json` — переносимый запуск через `${workspaceFolder}`, не секрет.

## Инструменты

| Инструмент | Что делает |
|---|---|
| [`get_issue`](#get_issue) | Читает задачу по ключу или URL |
| [`create_issue`](#create_issue) | Создаёт задачу, опционально привязывает к эпику |
| [`update_issue`](#update_issue) | Меняет тип, название, описание, Story Points |
| [`get_comments`](#get_comments) | Список комментариев задачи |
| [`create_comment`](#create_comment) | Добавляет комментарий |
| [`update_comment`](#update_comment) | Правит существующий комментарий |
| [`link_issue`](#link_issue) | Связывает две задачи (по умолчанию с эпиком) |
| [`get_project_epics`](#get_project_epics) | Эпики проекта |
| [`get_epic_issues`](#get_epic_issues) | Задачи эпика |
| [`get_issue_links`](#get_issue_links) | Все связи задачи |

Ключи, проекты и очереди ниже — вымышленные примеры (`KRA`, `VEL`, `ORB`), не очереди Tracker.

### get_issue

Принимает ключ (`KRA-417`) или URL (`https://tracker.yandex.ru/KRA-417`) и возвращает:

```json
{
  "key": "KRA-417",
  "summary": "...",
  "description": "...",
  "type": "Backend",
  "storyPoints": 5,
  "parent": {"key": "KRA-28", "summary": "..."},
  "epic": {"key": "VEL-1904", "summary": "..."},
  "comments": [{"id": "14082", "text": "...", "createdAt": "...", "updatedAt": "..."}]
}
```

`parent` и `epic` — `null`, если связи нет.

### create_issue

Принимает тип, название и текст задачи. Необязательные `epic` и `story_points`. Для бэкенд-задач (`backend` / `be` / `бэкенд`) в название добавляется префикс `BE:`, тип ставится `Backend`. Для фронтенд-задач (`frontend` / `fe` / `фронтенд`) — префикс `FE:` и тип `Frontend`. Алиасы: `qa` → `QA`, `ошибка` / `bug` / `error` → `Ошибка`, `автотесты` / `autotest` → `Автотесты`, `задача` / `task` → `Задача`. Префиксы вроде `[QA MT]` не добавляются автоматически. `epic` привязывает задачу к эпику (`has epic`).

### update_issue

Меняет тип, название, текст и/или Story Points. Те же правила для `BE:` / `FE:`. При смене типа снимается префикс **старого** типа. Пример смены типа: `issue_type=Задача`. Пример оценки: `story_points=5`.

### get_comments

Принимает ключ или URL задачи и возвращает комментарии без авторов:

```json
{
  "key": "KRA-417",
  "comments": [
    {"id": "14082", "text": "...", "createdAt": "...", "updatedAt": "..."}
  ]
}
```

### create_comment

Добавляет комментарий (`issue`, `text`). Возвращает whitelist-поля комментария. Пустой текст недопустим.

### update_comment

Правит существующий комментарий (`issue`, `comment_id`, `text`). Возвращает whitelist-поля. Пустой текст недопустим.

### link_issue

Связывает существующую задачу с другой. По умолчанию `relationship=has epic` (привязка к эпику). Пример: `issue=KRA-851`, `target=VEL-1904`.

### get_project_epics

Принимает ID проекта (`48219`) или URL (`https://tracker.yandex.ru/pages/projects/48219/`) и возвращает эпики проекта:

```json
{
  "project": "48219",
  "epics": [
    {"key": "KRA-73", "summary": "...", "type": "Epic", "status": "Open", "storyPoints": 8}
  ]
}
```

### get_epic_issues

Принимает ключ или URL эпика (`VEL-1904`) и возвращает задачи эпика без описаний и комментариев:

```json
{
  "epic": "VEL-1904",
  "issues": [
    {"key": "KRA-318", "summary": "...", "type": "Backend", "status": "Open", "storyPoints": 5}
  ]
}
```

### get_issue_links

Возвращает все связи задачи (эпик, подзадача, related, depends, duplicate):

```json
{
  "key": "VEL-1904",
  "links": [
    {
      "relationship": "epic",
      "label": "Epic for",
      "direction": "outward",
      "key": "KRA-318",
      "summary": "...",
      "status": "Open"
    }
  ]
}
```

## Cursor

Проектный конфиг лежит в `.cursor/mcp.json` и едет вместе с репозиторием. Глобальный вариант для всех чатов — в разделе [Перенос на другой компьютер](#перенос-на-другой-компьютер).
