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
    python app.py
    ```

### Features

1. Predefined student list
2. Automatic renaming
3. Only one submission per IP
4. Submission management (stop accepting submissions, delete individual/all submissions etc.)
5. Export to CSV

### Pages

There are three pages

1. `/_admin`: admin stuff
2. `/`: submission form
3. `/submitted`: submission confirmation
