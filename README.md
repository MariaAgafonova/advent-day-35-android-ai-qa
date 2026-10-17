# День 35 — Android AI QA

Локальный Python-агент исследует экран Android-приложения «На сегодня». DeepSeek выбирает отдельные действия, официальный Maestro MCP исполняет их на видимом эмуляторе. Результаты проверяются по UI-дереву и Maestro assertions; сохраняются скриншоты, отчёты и YAML для повторного запуска без LLM.

## Установка на этой машине (Windows PowerShell)

```powershell
cd D:\AIAdvent\advent-day-35-android-ai-qa
.\setup.ps1 -DownloadMaestro
.\tools\android-ai-qa\.venv\Scripts\Activate.ps1
Copy-Item .env.example .env
```

Заполните локальный `.env`. Он читается **только** при `--env-file .env`; без этого используется окружение процесса. Ключ не копируется из других проектов автоматически и не передаётся дочернему Maestro. Python ≥3.11; проверенная среда Python 3.12, Java 21, SDK `D:\AndroidSDK`. Установка не требует администратора. `uv.lock` фиксирует транзитивные зависимости; `uv sync --frozen` не обновляет их.

Maestro закреплён на официальном Windows release 2.11.0; setup проверяет SHA-256 архива. Если установка запрещена или бинарника нет, doctor сообщает причину и инструкции. WSL и самописный Node.js-сервер не используются.

## Подготовка эмулятора и приложения

Откройте AVD **NaTodayCalendarTest** в Android Studio Device Manager и оставьте окно видимым. Альтернатива:

```powershell
android emulator start NaTodayCalendarTest
D:\AndroidSDK\platform-tools\adb.exe devices -l
.\gradlew.bat :app:assembleDebug
python -m android_qa install-apk --device emulator-5554 --apk app/build/outputs/apk/debug/app-debug.apk
```

ID берётся из фактического `adb devices`, он может отличаться. При нескольких устройствах обязателен `--device`. Физическое устройство всегда требует явного выбора. Запуск сценария не переустанавливает APK. Основные проверки допускают только debuggable APK; приложение без регистрации, тестовый аккаунт не нужен. Для других приложений с авторизацией сессию нужно вручную подготовить, не помещая секреты в flows.

Android-проект: один модуль `app`, applicationId `ru.natoday.app`, Compose, Room, DataStore, debug/release. Сборочные версии находятся в `gradle/libs.versions.toml`. AGP 8.5.2 предупреждает о compileSdk 36; сборка на этой машине проходит. Исходная README сохранена в `docs/app`, но версии в ней исторически устарели.

## Запуск

После активации venv, из корня проекта:

```powershell
python -m android_qa doctor --device emulator-5554 --env-file .env
python -m android_qa doctor --check-api --device emulator-5554 --env-file .env
python -m android_qa run --device emulator-5554 --app-id ru.natoday.app --repo . --env-file .env --goal "Создай задачу и перенеси её на завтра"
python -m android_qa suite --device emulator-5554 --env-file .env
python -m android_qa suite --device emulator-5554 --env-file .env --scenario lifecycle
python -m android_qa replay --device emulator-5554 --flow qa/flows/create-task.yaml
```

Локальный веб-клиент показывает основные и дополнительные сценарии, последний результат, текущий этап, ошибки проверок и привязанные скриншоты. Запускайте его из активированного venv; сервер привязывается только к loopback:

```powershell
python -m android_qa web --device emulator-5554 --app-id ru.natoday.app --env-file .env --port 8765
```

Откройте `http://127.0.0.1:8765`. Веб-клиент разрешает только один активный сценарий на выбранном устройстве. Карточка показывает статусы `passed`, `failed`, `blocked`, `not_checked`; ошибки и скриншоты доступны в деталях запуска. Отчёт содержит полный список доказательств. Остановите сервер `Ctrl+C`.

`doctor --check-api` расходует API-квоту: текст, tool calling с ответом инструмента, изображение и изображение вместе с tools. Поддержка проверяется для выбранной модели. `deepseek-flash` — значение примера; модель и необязательная отдельная vision-модель настраиваются. Старый alias из пользовательского env-файла не заменяется молча. Стоимость не вычисляется.

В консоли: шаг, действие, проверка и путь к отчёту. Движения видны в Android Emulator. Во время живой MCP-сессии также может быть доступен локальный Maestro Viewer: http://127.0.0.1:9999/; основной наблюдаемый экран — окно эмулятора.

Новый сценарий всегда создаёт собственную `AIQA-<run-id>-<scenario>`. Четыре сценария независимы. `lifecycle` дополнительный. Очистка `passed` удаляет только собственную задачу после успешного сценария, `always` пытается очистить при ошибке, `never` оставляет данные. Скрытые другой датой/фильтром задачи не удаляются вслепую; это отражается в отчёте. Данные прежних запусков не считаются собственными текущему запуску.

Приоритет: CLI → переменные окружения → YAML → defaults. Все поля Settings доступны как `ANDROID_QA_<FIELD>`; DeepSeek использует `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`, `DEEPSEEK_MODEL`, `DEEPSEEK_VISION_MODEL`. Пример YAML — `qa/config.example.yaml`, параметр `--config`. По умолчанию 100 действий, 15 минут, 120 API-попыток и 200000 токенов на сценарий. Ctrl+C завершает MCP и сохраняет частичный результат. После неопределённого таймаута действие не повторяется автоматически.

## Файлы и архитектура

`tools/android-ai-qa/src/android_qa`: CLI/config → agent → DeepSeek / Maestro SDK → observations/checks → reports/flow_exporter. В `file_tools` локальный SQLite FTS-поиск, чтение с хешами и staging документации. Runtime полностью Python. Источники переиспользования: `docs/provenance.md`.

Режим A — по цели изучить документацию, код и тесты и создать непроверенный flow:

```powershell
python -m android_qa generate --repo . --env-file .env --goal "Создай Maestro flow проверки создания задачи"
```

Режим B — после прогона отчёт и предложение QA-документации сохраняются в артефактах. Просмотр/применение:

```powershell
python -m android_qa docs-diff --repo . --report artifacts/android-qa/<run-id>
python -m android_qa docs-apply --repo . --report artifacts/android-qa/<run-id>
```

`docs-apply` — явное действие пользователя после просмотра `proposals/changes.patch`; проверяются исходный хеш, путь и незакоммиченные изменения. Исходный Android-код автоматически не исправляется. Без исходников используйте `run --black-box`: анализ кода будет отмечен недоступным. Встроенные сценарные требования ориентированы на «На сегодня»; для другого продукта нужны его подтверждённые требования, неизвестное нельзя считать проверенным.

## Доказательства и ограничения

`artifacts/android-qa/<run-id>/`: `run.json`, `events.jsonl`, `checks.json`, `report.md`, `screenshots/`, `hierarchy/`, `logs/`, `generated-flows/`, `proposals/`. Manifest содержит цель, APK, устройство/API, locale/timezone/font scale, Git state, модель/capabilities и usage. Отчёты локальны и исключены из Git.

`passed` требует конкретного предиката и evidence. `failed` — наблюдаемое несоответствие; причина приложения требует отдельного подтверждения. `blocked` — препятствие выполнения; `not_checked` — нет достаточных доказательств. Ошибки API/MCP не являются багами приложения. Vision-выводы сохраняются как предварительные. Bounds не доказывают контрастность, dp-размеры или отсутствие наложения. Без vision остаются функциональные проверки и скриншоты.

Скриншоты, видимые тексты и разрешённые фрагменты исходников могут отправляться DeepSeek. Не используйте production-данные. Ключи, пароли, полные API-запросы и скрытые рассуждения в журнал не записываются. Артефакты могут содержать видимые данные экрана; храните их локально.

Maestro Android inputText не поддерживает Unicode в проверенной версии. Кириллица поэтому не считается пройденной при ASCII-вводе. Продукт не задаёт предел длинного названия; это `unspecified`. Отсутствие задачи/дублей проверяется только при полном покрытии списка, включая выполненные. При большом списке и недостаточном покрытии результат остаётся непроверенным.

Дополнительные профили: `run --profile small`, `--profile large-font`, `--profile dark`. Только эмулятор; настройки восстанавливаются в finally. После принудительного завершения ОС проверьте `device-restore.json` и восстановите указанные исходные значения вручную.

## Разработка и проверки

```powershell
uv sync --project tools/android-ai-qa --frozen
python -m pytest tools/android-ai-qa/tests -q
.\gradlew.bat :app:testDebugUnitTest :app:lintDebug :app:assembleDebug :app:assembleDebugAndroidTest
```

Автотесты Python используют явно обозначенные mock API/MCP. Они не означают прохождение приложения. Реальные прогоны перечислены в `docs/verification.md`. Существующие `connectedDebugAndroidTest` очищают БД приложения — на сохраняемом AVD их не запускайте. Перезапуск экспортированных flows не использует DeepSeek; неподтверждённый replay всегда `unverified`.
