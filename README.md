# Yandex Tracker MCP

Локальный MCP-сервер по stdio. Его запускает любой клиент, который умеет стартовать процесс: Cursor, Claude Code, Claude Desktop и другие. Сервер читает, создаёт и обновляет задачи Yandex Tracker, оставляет и правит комментарии, отдаёт состав эпика, эпики проекта и связи задачи. В ответ уходят только ключ, тип, Story Points, заголовок, описание, ссылки parent/epic, комментарии (id, текст, даты) и связи без персональных данных. Исполнитель, авторы и другие персональные поля не возвращаются.

Сам процесс порт не слушает и токен из конфига клиента не берёт. Токен и org ID лежат в `.env` рядом с кодом.

## Установка

Код переносится через git. Не копируйте `.venv` и `.env`: окружение собирается на машине, токен в git не кладётся.

Нужны [uv](https://docs.astral.sh/uv/getting-started/installation/) и свой `YANDEX_TRACKER_TOKEN` с `YANDEX_TRACKER_ORG_ID`. Python 3.13 ставит `uv`.

```bash
git clone https://github.com/damu4/yandex-tracker-mcp.git
cd yandex-tracker-mcp
cp .env.example .env
uv python install 3.13
uv sync --group dev
```

## Настройка

Скопируйте переменные из `.env.example`:

```bash
cp .env.example .env
```

Заполните `YANDEX_TRACKER_TOKEN` и `YANDEX_TRACKER_ORG_ID`. Очередь по умолчанию задаётся `YANDEX_TRACKER_QUEUE` (в `.env.example` — пример имени очереди).

Токен — IAM-токен Yandex Cloud. Установите [Yandex Cloud CLI](https://yandex.cloud/ru/docs/cli/quickstart#install), пройдите `yc init` из той же инструкции и выполните:

```bash
yc iam create-token
```

Вставьте вывод в `YANDEX_TRACKER_TOKEN`. Org ID возьмите в Tracker: **Администрирование → Организации → ID**.

IAM-токены (`t1.…`) быстро протухают. Если Tracker отвечает `403 Organization is not available`, обновите токен той же командой и проверьте, что org ID относится к той же организации.

Создайте окружение Python 3.13 через uv и установите пакет:

```bash
uv sync --group dev
```

Проверки кода:

```bash
uv run pytest
uv run ruff check src tests
uv run ruff format --check src tests
```

Проверка, что сервер вообще стартует на этой машине (без Cursor и без Claude):

```bash
uv run python -c "from yandex_tracker_mcp.server import mcp; print(', '.join(sorted(t.name for t in mcp._tool_manager.list_tools())))"
```

Должен напечататься список инструментов, включая `get_issue` и `create_comment`. Если команда падает на импорте, на этой машине клиент MCP тоже не запустится. `pytest` сеть Tracker не вызывает: зелёные тесты значат, что пакет собирается, а не что токен валиден.

Живой доступ к Tracker проверяется уже из клиента: после подключения MCP прочитайте любую задачу, к которой есть доступ у токена.

## Подключение

Клиент запускает одну и ту же команду:

```bash
uv run --directory /path/to/yandex-tracker-mcp python -m yandex_tracker_mcp
```

Общий фрагмент. Подставьте путь к клону. Если у графического клиента другой `PATH` и он не находит `uv`, в `command` укажите абсолютный путь (`which uv`).

```json
{
  "mcpServers": {
    "yandex-tracker": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/path/to/yandex-tracker-mcp",
        "python",
        "-m",
        "yandex_tracker_mcp"
      ],
      "env": {
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

`PYTHONUNBUFFERED` только отключает буфер вывода, чтобы клиент сразу видел ошибки. Сервер эту переменную не читает.

Секреты в JSON не дублируйте.

### Cursor

В репозитории уже есть [`.cursor/mcp.json`](.cursor/mcp.json). Cursor сам подставляет `${workspaceFolder}` — каталог, в котором открыт проект. После открытия папки перезапустите MCP в Cursor.

Чтобы сервер был во всех чатах, тот же фрагмент кладётся в `~/.cursor/mcp.json`. Удобно писать `${userHome}/yandex-tracker-mcp`, если клон лежит в домашней папке. Эти подстановки понимает только Cursor.

### Claude Code

Claude Code подстановки `${workspaceFolder}` не делает: в JSON нужен абсолютный путь. Запись живёт в `~/.claude.json`, секция `mcpServers`. Туда же пишет команда из корня клона:

```bash
claude mcp add --scope user yandex-tracker -- "$(which uv)" run --directory "$(pwd)" python -m yandex_tracker_mcp
```

Тот же фрагмент вручную:

```json
{
  "mcpServers": {
    "yandex-tracker": {
      "command": "/home/user/.local/bin/uv",
      "args": [
        "run",
        "--directory",
        "/home/user/yandex-tracker-mcp",
        "python",
        "-m",
        "yandex_tracker_mcp"
      ],
      "env": {
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

Перезапустите `claude`. Проверка: `claude mcp list`. Инструменты в сессии называются `mcp__yandex-tracker__*`.

### Claude Desktop

Это отдельное приложение и отдельный файл. Тот же JSON, что у Claude Code:

- Linux: `~/.config/Claude/claude_desktop_config.json`
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

Добавьте `mcpServers` в уже существующий объект, не затирая остальные ключи. Полностью закройте Desktop и откройте снова. Если Desktop не используете, этот файл можно не трогать: отсутствие секции `mcpServers` там нормально.

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
