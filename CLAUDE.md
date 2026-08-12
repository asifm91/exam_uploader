# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A [NiceGUI](https://nicegui.io/) web app that lets students submit exam work (project files + a mandatory screen-recording video, used as an anti-cheating measure) directly to a server, replacing a Google Form workflow that choked on large video uploads. One instructor-run instance manages multiple courses, each with multiple exams; each exam defines its own dynamic set of submission fields.

## Commands

```sh
pipenv install          # install dependencies (see Pipfile: nicegui, python 3.12)
pipenv run python main.py          # run in lab mode (default): reload off, wide reconnect window — use for real exams
pipenv run python main.py --dev    # run in dev mode: hot-reload on file changes, auto-opens a browser tab
pipenv run python main.py --host <host> --port <port>   # override bind address/port (default 0.0.0.0:8080)
```

There is no test suite or linter configured in this repo. `python -m py_compile <file>.py` is a reasonable smoke check after edits; beyond that, verify by actually running the app (`pipenv run python main.py --dev`) and exercising the relevant page in a browser.

## Architecture

**Entry point is `main.py`**, which imports `admin_page` and `submission_page` (each registers its own `@ui.page(...)` routes as a side effect of being imported) and makes the single `ui.run(...)` call. `admin_page.py` also has its own `if __name__ == "__main__": ui.run(...)` at the bottom — that's a leftover from before the multi-course rewrite and is not how the app is actually started; don't treat it as a second entry point.

**Routes**: `/` (public exam list + per-exam student submission stepper, in `submission_page.py`), `/admin` (login-gated course/exam management) and `/admin/exams/{exam_id}` (per-exam submission management, CSV/ZIP export), both in `admin_page.py`.

**Data model (`models.py`)**: plain dataclasses — `Course` → `Student` list, `Exam` (belongs to a `Course`, has `submissions` and `resource_files`), `Submission` (belongs to an `Exam` + `Student`, has a list of `Field`), `Field` (`FieldType`: text/pdf/zip/video). Each dataclass has a `render_ui()` method that draws its own NiceGUI card/UI — the UI is defined on the model, not in a separate view layer. IDs (`C####`/`E####`/`S####`) are auto-incrementing counters stored in `app.storage.general`.

**Persistence**: there's no database. `admin_page.py` hand-serializes the in-memory `courses`/`exams` lists to/from plain dicts (`_serialize_course`/`_deserialize_course`, `_serialize_exam`/`_deserialize_exam`) and stores them as JSON in `app.storage.general["courses"|"exams"]`, which NiceGUI persists to disk under `.nicegui/`. `load_all_data()` (called at the top of `/admin` and lazily by `get_exams()`/`get_exam()`) rehydrates the module-level `courses`/`exams` lists from storage — always go through `save_courses()`/`save_exams()` after mutating them, and through `get_exams()`/`get_exam(id)` to read them, rather than touching the module-level lists directly, since callers can't assume they're already loaded.

**Uploaded files** live on disk, not in storage: student submissions go under `submissions/<year>-<semester>-<course_code>-<section>--<exam_title>/`, exam resource files under `resources/<exam_id>/`, and admin CSV/ZIP exports under `downloads/` (all gitignored). The filename encodes course/exam/student/field for traceability — see `save_uploaded_file()` in `submission_page.py`.

**Single-event-loop constraint**: NiceGUI serves every connected client off one shared asyncio event loop, so any blocking (synchronous) disk/CPU work inside an `on_click`/event handler stalls *all* connected clients for its duration — this has directly caused student disconnects during live exams. `ui.upload`'s own `.save()` is already safe (NiceGUI offloads it internally), but hand-written blocking work in handlers is not offloaded automatically. The existing pattern for anything nontrivial (zipping submissions, deleting files/directories) is: make the handler `async def` and wrap the blocking call with `await run.io_bound(sync_fn, *args)` (see `download_csv`/`download_zip`/the delete and reset confirm handlers in `admin_page.py`). Follow this pattern for any new handler that touches the filesystem for more than a trivial read.

**Auth**: two independent, unrelated password gates, both plaintext strings in `app.storage.general` defaulting to `"admin"` if unset — `admin_passphrase` for `/admin`, checked in `admin_page.py`'s `create_admin_panel()`. There is no user-facing student auth; a student just picks their name from the course roster.
