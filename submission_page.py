"""
Student submission pages for exams.
"""

import uuid
from pathlib import Path

from nicegui import ui

from admin_page import get_exam, get_exams, save_exams
from models import Exam, Field, FieldType, Student, Submission


def get_submissions_dir(exam: Exam) -> Path:
    """Get the submissions directory path for an exam."""
    dir_name = f"{exam.course.year}-{exam.course.semester}-{exam.course.course_code}-{exam.course.section}--{exam.title}"
    submissions_dir = Path("submissions") / dir_name
    submissions_dir.mkdir(parents=True, exist_ok=True)
    return submissions_dir


async def save_uploaded_file(
    exam: Exam, student: Student, field_name: str, uploaded_file: ui.upload.FileUpload
) -> str:
    """Save an uploaded file with the specified naming scheme and return the file path."""
    submissions_dir = get_submissions_dir(exam)

    # Get original filename from upload result
    original_filename = uploaded_file.name
    file_ext = Path(original_filename).suffix
    short_id = f"{uuid.uuid4().hex[:6]}"

    # Generate new filename: <year>-<semester>-<course_code>-<section>--<exam_name>--<student_id>-<field_name>--<hash><ext>
    new_filename = f"{exam.course.year}-{exam.course.semester}-{exam.course.course_code}-{exam.course.section}--{exam.title}--{student.id}-{field_name}--{short_id}{file_ext}"

    file_path = submissions_dir / new_filename

    # Save the file using the built-in save method
    await uploaded_file.save(str(file_path))

    # Return relative path for storage
    return str(file_path)


@ui.page("/")
def home_page():
    """Home page listing all available exams."""
    # Load data from storage
    exams = get_exams()

    with ui.column().classes("w-full gap-4 p-4 max-w-4xl mx-auto"):
        ui.label("Exam Submissions").classes("text-3xl font-bold mb-6")

        # Open exams section
        open_exams = [e for e in exams if e.is_accepting]
        with ui.card().classes("w-full"):
            ui.label("🟢 Open for Submission").classes("text-2xl font-bold mb-4")

            if open_exams:
                with ui.grid(columns="repeat(auto-fill, minmax(300px, 1fr))").classes(
                    "w-full gap-4"
                ):
                    for exam in open_exams:
                        render_exam_list_item(exam)
            else:
                ui.label("No exams currently open for submission").classes(
                    "text-gray-400 text-center py-8"
                )

        ui.separator()

        # Closed exams section
        closed_exams = [e for e in exams if not e.is_accepting]
        with ui.card().classes("w-full"):
            ui.label("🔴 Closed to Submission").classes("text-2xl font-bold mb-4")

            if closed_exams:
                with ui.grid(columns="repeat(auto-fill, minmax(300px, 1fr))").classes(
                    "w-full gap-4"
                ):
                    for exam in closed_exams:
                        render_exam_list_item(exam, disabled=True)
            else:
                ui.label("No closed exams").classes("text-gray-400 text-center py-8")


def render_exam_list_item(exam: Exam, disabled: bool = False):
    """Render an exam item in the list."""
    with ui.card().classes("w-full"):
        ui.label(exam.title).classes("text-lg font-bold")
        ui.label(f"{exam.course.course_code} - Section {exam.course.section}").classes(
            "text-sm text-gray-600"
        )
        ui.label(f"{exam.course.semester} {exam.course.year}").classes(
            "text-sm text-gray-600 mt-2"
        )

        if disabled:
            ui.button("Closed").props("disabled").classes("w-full mt-4")
        else:
            ui.button(
                "Open Submission Form",
                icon="dynamic_form",
                on_click=lambda eid=exam.id: ui.navigate.to(f"/{eid}"),
            ).classes("w-full mt-4")


@ui.page("/{exam_id}")
def submission_page(exam_id: str):
    """Submission form page for a specific exam with stepper."""
    exam = get_exam(exam_id)

    if not exam:
        ui.label("Exam not found").classes("text-red-600 p-4")
        ui.button(
            "Back to Exams", icon="arrow_back", on_click=lambda: ui.navigate.to("/")
        )
        return

    # Check if exam is accepting submissions
    if not exam.is_accepting:
        with ui.column().classes("w-full gap-4 p-4 max-w-2xl mx-auto"):
            ui.label(f"{exam.title}").classes("text-2xl font-bold")
            ui.label("This exam is no longer accepting submissions").classes(
                "text-orange-600 text-lg mt-4 p-4 bg-orange-50 rounded"
            )
            ui.button(
                "Back to Exams", icon="arrow_back", on_click=lambda: ui.navigate.to("/")
            )
        return

    with ui.column().classes("w-full gap-4 p-4 max-w-2xl mx-auto"):
        # Header
        with ui.row().classes("items-center justify-between mb-4"):
            with ui.column().classes("flex-grow"):
                ui.label(exam.title).classes("text-2xl font-bold")
                ui.label(
                    f"{exam.course.course_code} - Section {exam.course.section}"
                ).classes("text-gray-600")
            ui.button("Back", icon="arrow_back", on_click=lambda: ui.navigate.to("/"))

        ui.separator()

        # Resource Files Section
        if exam.resource_files:
            with ui.card().classes("w-full"):
                ui.label("📎 Resource Files").classes("text-lg font-bold mb-4")
                with ui.column().classes("w-full gap-2"):
                    for resource in exam.resource_files:
                        with ui.row().classes("items-center gap-2 p-2"):
                            # ui.icon("download").classes("text-blue-600")
                            ui.label(resource["name"]).classes("text-sm flex-grow")
                            ui.button(
                                "Download",
                                icon="download",
                                on_click=lambda path=resource["path"]: ui.download(
                                    path
                                ),
                                color="primary",
                            ).props("flat no-caps").classes("text-sm")

        # Create student list from course
        student_options = {s: str(s) for s in exam.course.student_list}

        # Stepper
        with ui.stepper().classes("w-full") as stepper:
            # Step 1: Student Selection
            ss = [None]
            with ui.step("Student Information"):
                ui.label("Select your information").classes(
                    "text-lg font-semibold mb-4"
                )

                student_select = ui.select(
                    student_options,
                    label="Select Your Name and ID",
                ).classes("w-full")

                already_submitted_msg = ui.label().classes("mt-4 text-orange-600")

                def check_submission():
                    # Check if exam is still accepting submissions
                    if not exam.is_accepting:
                        ui.notify(
                            "This exam is no longer accepting submissions",
                            type="warning",
                        )
                        already_submitted_msg.set_text(
                            "⚠️ This exam is closed for submissions"
                        )
                        return

                    if not student_select.value:
                        ui.notify("Please select a student", type="warning")
                        return

                    selected_student = student_select.value

                    # Check if student already submitted
                    existing_submission = next(
                        (
                            s
                            for s in exam.submissions
                            if s.student.id == selected_student.id
                        ),
                        None,
                    )

                    if existing_submission:
                        already_submitted_msg.set_text(
                            f"⚠️ You already submitted on {existing_submission.submission_date.strftime('%Y-%m-%d %H:%M')}"
                        )
                        ui.notify(
                            "This student already has a submission", type="warning"
                        )
                        return
                    else:
                        display_selected_student.refresh()

                        already_submitted_msg.set_text("")
                        stepper.next()

                ui.button("Next", on_click=check_submission).classes("w-full mt-4")

            # Step 2: Form Input
            with ui.step("Submission Fields"):
                ui.label("Fill in the submission details").classes(
                    "text-lg font-semibold mb-4"
                )

                # Display selected student info
                @ui.refreshable
                def display_selected_student():
                    if student_select.value:
                        selected_student_info = student_select.value
                        with ui.card().classes("w-full mb-4 bg-blue-50"):
                            with ui.row().classes("items-center gap-4"):
                                ui.icon("person").classes("text-blue-600 text-2xl")
                                with ui.column():
                                    ui.label(selected_student_info.name).classes(
                                        "text-lg font-semibold"
                                    )
                                    ui.label(f"ID: {selected_student_info.id}").classes(
                                        "text-sm text-gray-600"
                                    )

                display_selected_student()

                # Get the template submission with field definitions
                template_submission = next(
                    (s for s in exam.submissions if not s.student.id), None
                )
                submission_fields = {}
                uploaded_files = {}  # Store file paths with (field_name) -> file_path

                if template_submission and template_submission.data:
                    for field in template_submission.data:
                        if field.type.value == "text":
                            submission_fields[field.name] = ui.input(
                                label=field.name,
                                placeholder=f"Enter {field.name.lower()}",
                            ).classes("w-full")
                        else:  # pdf, zip, or video

                            async def on_file_upload(
                                e, fname=field.name, ftype=field.type
                            ):
                                """Handle file upload and save to disk."""
                                try:
                                    file_path = await save_uploaded_file(
                                        exam, student_select.value, fname, e.file
                                    )
                                    # Store both original filename and saved filepath
                                    uploaded_files[fname] = {
                                        "original_filename": e.file.name,
                                        "saved_filepath": file_path,
                                    }
                                    ui.notify(
                                        f"File uploaded: {e.file.name}", type="positive"
                                    )
                                    print(f"File saved to: {file_path}")
                                except Exception as ex:
                                    ui.notify(
                                        f"Error uploading file: {str(ex)}",
                                        type="negative",
                                    )
                                    print(f"Upload error: {ex}")

                            # Get allowed extensions for this field type
                            allowed_extensions = FieldType.get_file_extensions(
                                field.type
                            )
                            accept_attr = ",".join(allowed_extensions)

                            submission_fields[field.name] = (
                                ui.upload(
                                    label=field.name,
                                    on_upload=on_file_upload,
                                    auto_upload=True,
                                )
                                .props(f'accept="{accept_attr}"')
                                .classes("w-full")
                            )

                # Status message
                status_message = ui.label().classes("mt-4")

                # Submit button
                def handle_submit():
                    # Check if exam is still accepting submissions
                    if not exam.is_accepting:
                        status_message.set_text(
                            "❌ This exam is no longer accepting submissions"
                        )
                        status_message.classes(
                            add="text-red-600", remove="text-green-600"
                        )
                        return

                    if not student_select.value:
                        status_message.set_text("❌ Student not selected")
                        status_message.classes(
                            add="text-red-600", remove="text-green-600"
                        )
                        return

                    selected_student = student_select.value

                    # Validate submission fields
                    if template_submission and template_submission.data:
                        for field in template_submission.data:
                            if field.name not in submission_fields:
                                status_message.set_text(
                                    f"❌ Missing field: {field.name}"
                                )
                                status_message.classes(
                                    add="text-red-600", remove="text-green-600"
                                )
                                return

                            if field.type.value == "text":
                                field_value = submission_fields[field.name].value
                                if not field_value:
                                    status_message.set_text(
                                        f"❌ Please fill in {field.name}"
                                    )
                                    status_message.classes(
                                        add="text-red-600", remove="text-green-600"
                                    )
                                    return
                            else:  # pdf, zip, or video
                                if field.name not in uploaded_files:
                                    status_message.set_text(
                                        f"❌ Please upload a file for {field.name}"
                                    )
                                    status_message.classes(
                                        add="text-red-600", remove="text-green-600"
                                    )
                                    return

                    # Create submission
                    submission_data = []

                    if template_submission and template_submission.data:
                        for field in template_submission.data:
                            if field.type.value == "text":
                                field_value = submission_fields[field.name].value
                                submission_data.append(
                                    Field(
                                        name=field.name,
                                        type=field.type,
                                        value=str(field_value) if field_value else "",
                                    )
                                )
                            else:  # pdf, zip, or video
                                file_info = uploaded_files.get(field.name, {})
                                submission_data.append(
                                    Field(
                                        name=field.name,
                                        type=field.type,
                                        value=file_info.get("saved_filepath", ""),
                                        original_filename=file_info.get(
                                            "original_filename", ""
                                        ),
                                        saved_filepath=file_info.get(
                                            "saved_filepath", ""
                                        ),
                                    )
                                )

                    submission = Submission(
                        exam=exam, student=selected_student, data=submission_data
                    )
                    exam.submissions.append(submission)
                    save_exams()

                    # Show success message
                    status_message.set_text(
                        f"✓ Submission received! Thank you, {selected_student.name}."
                    )
                    status_message.classes(add="text-green-600", remove="text-red-600")

                    # Disable inputs
                    student_select.enabled = False
                    for field_input in submission_fields.values():
                        field_input.enabled = False
                    submit_button.enabled = False
                    back_button.enabled = False

                with ui.row().classes("gap-2 w-full"):
                    back_button = (
                        ui.button("Back", on_click=stepper.previous)
                        .props("outline")
                        .classes("flex-grow")
                    )
                    submit_button = ui.button("Submit", on_click=handle_submit).classes(
                        "flex-grow"
                    )


# To use this with your app, add this import to app.py:
# from submission import *  # or import submission
#
# Then remove the ui.run() from app.py and add:
# if __name__ in ("__main__", "__mp_main__"):
#     ui.run(storage_secret="secret")
