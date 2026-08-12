# Exam Uploader

A simple [NiceGUI](https://nicegui.io/) app that allows students to submit their work.

## Background

The students do mini projects for their exam. To prevent cheating, they are required to do screen recording and submit it along with their work. Previously, Google Form was being utilized which worked fine for just the project submission. However, since the video file can be quite huge, they face various difficulties submitting it via Google Form. 

- Upload not completed in time due to poor network
- Server rejected for various reasons
- Upload failed due to insufficient storage in student's Google Drive

To address these issues, I had the idea of creating a local web server in one of the lab PCs where students would drop their files. However, it is not quite suitable for exam scenarios

- Students could view each others files
- Students could manipulate others submissions
- Students could submit multiple times

Therefore a more complex setup is needed.

## Usage

### Installation

You need Python to run this app. I developed and tested on Python 3.12, but anything after 3.6 should be fine. 

You will also need [Pipenv](https://pipenv.pypa.io/en/latest/) to install dependencies

1. Clone/cownload the repository.
2. Go to the project folder in a terminal/command prompt
3. Install dependencies

    ```sh
    pipenv install
    ```

4. Activate virtual environment

    ```sh
    pipenv shell
    ```

5. Start the webserver (use `python3` in Linux)

    ```sh
    python main.py
    ```

    This starts the app in **lab mode**: hot-reload is disabled and the
    reconnect window is widened, so a code editor autosaving in the
    background or a brief wifi hiccup won't drop every connected student.
    Use this mode whenever the app is actually serving students.

    For local development, pass `--dev` to get hot-reload and an
    auto-opened browser tab:

    ```sh
    python main.py --dev
    ```

    `--host` and `--port` are also available if the lab needs a specific
    port opened in the firewall (defaults: `0.0.0.0:8080`).

### Features

1. Predefined student list
2. Automatic renaming
3. Only one submission per IP
4. Submission management (stop accepting submissions, delete individual/all submissions etc.)
5. Export to CSV

### Pages

1. `/`: list of exams open/closed for submission, with the student submission stepper for each open exam
2. `/admin`: login-gated admin panel for managing courses, students, and exams
3. `/admin/exams/{exam_id}`: manage a specific exam (accept/stop submissions, view student status, download CSV/ZIP, delete individual/all submissions)
