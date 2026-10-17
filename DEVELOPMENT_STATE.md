# Development checkpoint

Updated: 2026-10-17

## Project

Day 35 Android AI QA assistant, standalone repository at `D:\AIAdvent\advent-day-35-android-ai-qa`. The source Android app is `ru.natoday.app` (Compose, Room, DataStore). Work is based on source commit `1e647b509127aae7719e1d6fa8315936cfc93a42`; unrelated day 34 working changes were left untouched.

## Implemented and verified

- Python 3.12 package under `tools/android-ai-qa`, locked dependencies, Typer CLI, config, diagnostics, official Maestro MCP integration, DeepSeek client, sequential agent loop, evidence/check/report handling, guarded file access, flow export and replay, and documentation proposal workflow.
- Four independent task scenarios: create, move to next day, change status, and delete. Requirements and visual rules are under `qa/specs/`; reusable flows are under `qa/flows/`.
- Real run used visible AVD `NaTodayCalendarTest` / `emulator-5554`, Android API 35, Maestro 2.11.0, official Maestro MCP, and DeepSeek. Text, tool calling, image, and image-plus-tool-call capability probes passed. Vision is available for the tested model/configuration.
- All four scenarios passed against the real app. Each exported parameterized flow was replayed successfully on the same emulator; `artifacts/android-qa/verified-exports.json` records the results. Evidence and reports are retained locally under ignored `artifacts/android-qa/`.
- Python suite: 45 passed, including localized weekday and year-boundary calendar selector cases. Android `:app:testDebugUnitTest --rerun-tasks`: passed (25 tasks executed). The full Android build/lint/debug-test-APK checks also passed earlier.
- Follow-up fix: move-flow date selectors now match calendar day and month without a weekday, and navigate to the next month only when that date is not visible. The corrected flow replay passed twice on the real emulator with official Maestro MCP; latest evidence: `artifacts/android-qa/20261017T182459-31f1d6/`.
- No production Android source was changed. User data was not cleared; scenario cleanup only targets each run's uniquely named task.

## Current state and follow-up

- This repository had no commit before the checkpoint. The checkpoint commit contains the source, QA specs/flows, docs, and tests; local secrets, tool downloads, build products, virtualenv, and run artifacts remain ignored.
- Draft flow `qa/flows/draft-20261017T181754-71bc93.yaml` is intentionally unverified. Other unverified drafts are retained for inspection.
- Supplementary input/undo/device-profile variants were not run end-to-end. Android instrumentation tests were intentionally not run because the existing tests clear application data.
- Generated reports, screenshots, hierarchy, and logs are intentionally Git-ignored but remain on this machine. Do not treat those local paths as portable repository files.

## Resume

```powershell
cd D:\AIAdvent\advent-day-35-android-ai-qa
uv sync --project tools/android-ai-qa --frozen
.\tools\android-ai-qa\.venv\Scripts\Activate.ps1
python -m android_qa doctor --device emulator-5554 --env-file .env
python -m pytest tools/android-ai-qa/tests -q
```

For a fresh real run, start the visible AVD and provide a local `.env` with `DEEPSEEK_API_KEY`; then use `python -m android_qa suite --device emulator-5554 --env-file .env`. Do not commit `.env` or artifacts.
