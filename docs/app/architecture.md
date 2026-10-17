# Application architecture

NaToday («На сегодня») is an Android daily planner. It runs without registration or an application server. The app has one Gradle module, `app`, and uses Kotlin, Compose Material 3, ViewModel, StateFlow, Coroutines, Room, Preferences DataStore and Navigation Compose.

## Entry point and screens

`app/src/main/java/ru/natoday/app/MainActivity.kt` is the Android activity and hosts the Navigation Compose graph. Routes are today, review/{day}, voice/{day}, and settings. A notification carries an epoch-day date to the review route; the Today destination remains beneath it in the navigation back stack.

`ui/DayScreen.kt` contains the day list, task cards and evening review screen. `ui/PlannerViewModels.kt` owns task operations, selected date and review session counts. `ui/VoiceScreen.kt` and `ui/VoiceViewModel.kt` implement the editable voice preview. `ui/SettingsScreen.kt` controls reminder preferences. These paths are relative to `app/src/main/java/ru/natoday/app/`.

## Local persistence

`data/Task.kt` is a Room entity: id, title, scheduledDate, createdAt, completedAt. The planned date is LocalDate stored as epochDay. Creation and completion are Instant stored as epoch milliseconds. Time zone changes do not move tasks to a different calendar date.

`data/TaskDao.kt` exposes a Flow for a chosen date. `data/TaskRepository.kt` validates titles and implements create, rename, complete/uncomplete, move, delete and restore. Moving updates scheduledDate on the same row; it never creates a copy or marks a pending task completed. Undo deletion restores the original identifier.

`data/TaskDatabase.kt` is Room schema version 1. Exported schemas live in `app/schemas/`. `data/SettingsRepository.kt` stores reminder enabled/time and scheduling metadata in Preferences DataStore. Reminders default to disabled, time 22:00.

## State and dependency wiring

`PlannerApplication.kt` creates one Room database, repositories and ReminderScheduler. Dependencies are passed through ViewModel factories without a DI framework. UI collects StateFlow with lifecycle awareness. Each edit commits to Room immediately. Review transfer counts survive recreation via SavedStateHandle but reset for a new review session.

## Build from source

The repository root contains `settings.gradle.kts`, `build.gradle.kts`, `gradlew.bat` and `gradle/libs.versions.toml`. Open this root in Android Studio. Build a debug APK with `.\\gradlew.bat :app:assembleDebug`. Unit tests use `:app:testDebugUnitTest`, lint uses `:app:lintDebug`, device tests use `:app:connectedDebugAndroidTest`.

The Python developer assistant is optional and lives in `developer_assistant/`; Android does not call it. Its MCP server reads Git metadata of this same repository root. No GitLab CLI checkout is required.
