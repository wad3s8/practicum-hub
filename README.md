# Practicum Hub API

Внутренний backend для сотрудников банка, сопровождающих студенческие проектные практикумы.
Стек: Python 3.12, FastAPI, SQLAlchemy 2, PostgreSQL 17, Alembic, Docker Compose.
Точные версии Python-зависимостей зафиксированы в `constraints.txt`.

## Реализовано

- Авторизация сотрудников по email и паролю, JWT access token.
- Регистрация сотрудников администратором; роли `admin` и `curator`, отключение доступа.
- Проекты: создание, просмотр, фильтры, редактирование, удаление несвязанных записей.
- Студенты и справочник вузов; поиск по ФИО, предупреждение о возможных дублях.
- Команды и история участия студентов в них.
- `PROJECT_TEAM`: назначение команды на проект за период, статус и общий результат.
- Назначение кураторов на `PROJECT_TEAM` с историей участия.
- Миграции и интеграционные тесты на отдельной PostgreSQL-базе.

Встречи, серии, задачи, артефакты, SSO и внешние интеграции пока не реализованы.
Это API без отдельного frontend; взаимодействовать с ним можно через Swagger UI.

## Запуск в Docker

Из корня проекта в PowerShell:

```powershell
./scripts/init-env.ps1
docker compose up --build -d
docker compose exec api python -m app.bootstrap
```

Скрипт создаёт `.env` со случайными секретами, если файла ещё нет. Существующий файл не меняется.
Сервис `migrate` применяет миграции после готовности PostgreSQL; API стартует после успешной миграции.
Команда bootstrap интерактивно спрашивает имя, email и пароль первого администратора. Пароль вводится скрыто.
Повторное создание первого администратора при наличии активного администратора запрещено.

- Swagger UI: [http://localhost:8010/docs](http://localhost:8010/docs)
- OpenAPI: [http://localhost:8010/openapi.json](http://localhost:8010/openapi.json)
- Проверка API и соединения с БД: [http://localhost:8010/health](http://localhost:8010/health)

Порт хоста задаётся переменной `API_PORT` в `.env` (по умолчанию `8010`).

В Swagger нажмите **Authorize**. Поле `username` — email сотрудника; `password` — его пароль.
После входа используйте `POST /api/v1/auth/register`, чтобы создать кураторов или других администраторов.
Публичной регистрации и учётных записей студентов нет.

API доступен только на `127.0.0.1`; PostgreSQL не публикует порт на хост.
Данные основной базы сохраняются в volume `postgres_data`.

```powershell
docker compose logs -f api
docker compose stop
```

Переменные описаны в `.env.example`. Не используйте значения-заглушки: приложение отклоняет
заглушку JWT. Для пароля PostgreSQL, включаемого в URL, используйте случайную hex-строку,
как в скрипте инициализации. `.env` исключён из Git и Docker build context.

## API

Все предметные маршруты требуют `Authorization: Bearer <token>`. Префикс — `/api/v1`.
Активные сотрудники имеют общий доступ к предметным данным; назначения кураторов являются
учётными связями, а не правилами ограничения видимости. Создание аккаунтов и изменение
их доступа доступны только администратору. Его права также включают предметные операции.

| Маршрут | Методы | Назначение |
|---|---|---|
| `/auth/login` | POST | Вход; form-data `username=email`, `password` |
| `/auth/me` | GET | Текущий сотрудник |
| `/auth/register` | POST | Регистрация сотрудника администратором |
| `/accounts` | GET | Список сотрудников для выбора кураторов |
| `/accounts/{id}/access` | PATCH | Изменить роль или `is_active`, только администратор |
| `/universities` | GET, POST | Справочник вузов |
| `/universities/{id}` | PATCH, DELETE | Изменить или удалить вуз |
| `/students` | GET, POST | Список и создание студентов |
| `/students/{id}` | GET, PATCH, DELETE | Карточка студента |
| `/students/{id}/memberships` | GET | История команд студента |
| `/teams` | GET, POST | Список и создание команд |
| `/teams/{id}` | GET, PATCH, DELETE | Карточка команды |
| `/teams/{id}/members` | GET, POST | Состав команды |
| `/teams/{id}/members/{member_id}` | PATCH | Роль и даты участия студента |
| `/projects` | GET, POST | Список и создание проектов |
| `/projects/{id}` | GET, PATCH, DELETE | Карточка проекта |
| `/project-teams` | GET, POST | Назначения команд на проекты |
| `/project-teams/{id}` | GET, PATCH, DELETE | Период, статус, результат назначения |
| `/project-teams/{id}/curators` | GET, POST | Кураторы назначения |
| `/project-teams/{id}/curators/{curator_id}` | PATCH | Даты назначения куратора |

В последнем маршруте `curator_id` — ID записи `PROJECT_TEAM_CURATOR`, а не ID аккаунта.
Списки поддерживают `offset` и `limit` (по умолчанию 50, максимум 100).
Фильтры:

- студенты: `q` (ФИО), `university_id`, `team_id` (включая прошлое участие);
- команды: `q` (название);
- проекты: `q` (название), `status`;
- назначения: `project_id`, `team_id`, `curator_id` (ID аккаунта, включая прошлое участие), `period_name`, `status`;
- состав и кураторы: `active_only=true` — записи с незаполненным `left_on`.

## Пример последовательности

После регистрации куратора и входа под ним выполните запросы в Swagger.
В примерах используйте ID, полученные от предыдущих запросов, вместо условных `1`.

1. `POST /universities`: `{"name":"УрФУ"}`.
2. `POST /students`: `{"university_id":1,"full_name":"Иван Иванов","study_group":"РИ-101"}`.
3. `POST /teams`: `{"name":"Альфа"}`.
4. `POST /teams/1/members`: `{"student_id":1,"role":"developer","joined_on":"2026-09-01"}`.
5. `POST /projects`: `{"title":"Анализ обращений","description":"Прототип аналитики","expected_result":"Рабочий прототип"}`.
6. `POST /project-teams`: `{"project_id":1,"team_id":1,"period_name":"Осень 2026","starts_on":"2026-09-01","ends_on":"2026-12-31"}`.
7. `POST /project-teams/1/curators`: `{"account_id":2,"joined_on":"2026-09-01"}`.

У проекта `created_by` берётся из текущего аккаунта; передать его вручную нельзя.
Поля `owner_id` нет. У студентов отсутствуют поля аккаунта и пароля.

## История и валидация

- У студента стабильный числовой ID. Учебная группа может меняться и не является идентификатором.
- Совпадение ФИО, вуза и группы без учёта регистра возвращает `409` со списком возможных дублей.
  Для осознанного создания другой карточки используйте `?allow_duplicate=true`; автоматического объединения нет.
- Студент может одновременно состоять в разных командах. В одной команде допускается одна
  незавершённая запись его участия. Для выхода заполните `left_on`, для возвращения создайте новую запись.
- Смена проекта команды не создаёт заново её состав. Новый период — новая запись `PROJECT_TEAM`.
- Нельзя заменить команду или проект в существующем назначении: создайте новое назначение.
- Кураторы назначаются на `PROJECT_TEAM`; активное назначение одного куратора не дублируется.
- Дата окончания не может быть раньше даты начала. Даты периодов задаются явно.
- Проект: `active`, `completed`, `continuing`. Назначение команды: `active`, `completed`, `paused`.
- DELETE разрешён только если на запись нет ссылок. При наличии истории возвращается `409`.
  Состав и назначения кураторов не удаляются через API: участие завершается датой `left_on`.
- Завершение проекта или периода не удаляет студентов, команды и результаты.
- Access token действует 60 минут по умолчанию. Отключение аккаунта блокирует и уже выданные токены.
  Refresh tokens и восстановление пароля пока не входят в этот этап.

## Проверки

```powershell
docker compose --profile test build test
docker compose --profile test run --rm test
docker compose --profile test run --rm --no-deps test ruff check app tests migrations
docker compose --profile test stop test-db
```

Тесты запускаются на PostgreSQL, применяют реальные миграции и проверяют соответствие схемы моделям
командой `alembic check`. База `practicum_test` отделена от основной и хранится в tmpfs.
Перед каждым тестом очищается только тестовая база. Тесты отказываются работать с другим именем базы.

## Структура

```text
app/
  main.py        # FastAPI, роутеры, health
  config.py      # Настройки окружения
  db.py          # SQLAlchemy engine и сессии
  models.py      # Модели базы
  schemas.py     # Входные и выходные схемы
  security.py    # Argon2, JWT, зависимости доступа
  auth.py        # Вход, регистрация, управление доступом
  resources.py   # Предметные API
  services.py    # Общие операции сохранения и проверки
  bootstrap.py   # Первый администратор
migrations/      # Alembic
tests/           # Интеграционные тесты
scripts/         # Инициализация окружения
```

Авторизация использует JWT и Argon2 по [документации FastAPI](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/).
Доступ к PostgreSQL — через [SQLAlchemy и psycopg 3](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.psycopg).
