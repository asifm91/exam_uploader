"""
Admin panel with tabbed interface for managing courses and exams.
"""

import csv
import zipfile
from datetime import datetime
from pathlib import Path

from nicegui import app, run, ui

from models import Course, Exam, Field, FieldType, Student, Submission

courses = []
exams = []


def _serialize_course(course: Course) -> dict:
    """Serialize a Course object to a dictionary."""
    return {
        "id": course.id,
        "course_code": course.course_code,
        "section": course.section,
        "semester": course.semester,
        "year": course.year,
        "student_list": [
            {"id": student.id, "name": student.name} for student in course.student_list
        ],
    }


def _deserialize_course(data: dict) -> Course:
    """Deserialize a dictionary back to a Course object."""
    students = [
        Student(id=s["id"], name=s["name"]) for s in data.get("student_list", [])
    ]
    course = Course(
        course_code=data["course_code"],
        section=data["section"],
        semester=data["semester"],
        year=data["year"],
        student_list=students,
    )
    course.id = data["id"]  # Restore the original ID
    return course


def _serialize_exam(exam: Exam) -> dict:
    """Serialize an Exam object to a dictionary."""
    return {
        "id": exam.id,
        "title": exam.title,
        "course_id": exam.course.id,
        "start_time": exam.start_time.isoformat(),
        "end_time": exam.end_time.isoformat() if exam.end_time else None,
        "is_accepting": exam.is_accepting,
        "resource_files": exam.resource_files,  # [{name, path}, ...]
        "submissions": [
            {
                "id": sub.id,
                "student": {"id": sub.student.id, "name": sub.student.name},
                "submission_date": sub.submission_date.isoformat(),
                "data": [
                    {
                        "name": f.name,
                        "type": f.type.value,
                        "value": f.value,
                        "original_filename": f.original_filename,
                        "saved_filepath": f.saved_filepath,
                    }
                    for f in sub.data
                ],
            }
            for sub in exam.submissions
        ],
    }


def _deserialize_exam(data: dict, course_map: dict) -> Exam:
    """Deserialize a dictionary back to an Exam object."""
    course = course_map.get(data["course_id"])
    if not course:
        raise ValueError(f"Course {data['course_id']} not found")

    from datetime import datetime

    exam = Exam(
        title=data["title"],
        course=course,
        start_time=datetime.fromisoformat(data["start_time"]),
        end_time=datetime.fromisoformat(data["end_time"]) if data["end_time"] else None,
    )
    exam.id = data["id"]
    exam.is_accepting = data.get("is_accepting", True)
    exam.resource_files = data.get("resource_files", [])  # Restore resource files

    # Restore submissions
    for sub_data in data.get("submissions", []):
        student = Student(
            id=sub_data["student"]["id"], name=sub_data["student"]["name"]
        )
        fields = [
            Field(
                name=f["name"],
                type=FieldType[f["type"].upper()],
                value=f["value"],
                original_filename=f.get("original_filename", ""),
                saved_filepath=f.get("saved_filepath", ""),
            )
            for f in sub_data["data"]
        ]
        submission = Submission(
            exam=exam,
            student=student,
            data=fields,
            submission_date=datetime.fromisoformat(sub_data["submission_date"])
            if "submission_date" in sub_data
            else datetime.now(),
        )
        submission.id = sub_data["id"]
        exam.submissions.append(submission)

    return exam


def save_courses():
    """Save courses list to app.storage."""
    course_data = [_serialize_course(course) for course in courses]
    app.storage.general["courses"] = course_data


def load_courses():
    """Load courses from app.storage."""
    global courses
    course_data = app.storage.general.get("courses", [])
    courses = [_deserialize_course(data) for data in course_data]


def save_exams():
    """Save exams list to app.storage."""
    exam_data = [_serialize_exam(exam) for exam in exams]
    app.storage.general["exams"] = exam_data


def load_exams():
    """Load exams from app.storage."""
    global exams
    exam_data = app.storage.general.get("exams", [])
    course_map = {course.id: course for course in courses}
    exams = [_deserialize_exam(data, course_map) for data in exam_data]


def _update_id_counters():
    """Update ID counters after loading data."""
    # Update course counter
    max_course_id = 1000
    for course in courses:
        if course.id.startswith("C"):
            try:
                course_num = int(course.id[1:])
                max_course_id = max(max_course_id, course_num + 1)
            except ValueError:
                pass
    app.storage.general["course_id_counter"] = max_course_id

    # Update exam counter
    max_exam_id = 2000
    for exam in exams:
        if exam.id.startswith("E"):
            try:
                exam_num = int(exam.id[1:])
                max_exam_id = max(max_exam_id, exam_num + 1)
            except ValueError:
                pass
    app.storage.general["exam_id_counter"] = max_exam_id

    # Update submission counter
    max_submission_id = 3000
    for exam in exams:
        for submission in exam.submissions:
            if submission.id.startswith("S"):
                try:
                    sub_num = int(submission.id[1:])
                    max_submission_id = max(max_submission_id, sub_num + 1)
                except ValueError:
                    pass
    app.storage.general["submission_id_counter"] = max_submission_id


def load_all_data():
    """Load all courses and exams from storage."""
    load_courses()
    load_exams()
    _update_id_counters()


def get_exams():
    """Get the list of exams."""
    if not exams:
        load_all_data()
    return exams


def get_exam(id: str) -> Exam | None:
    """Get a specific exam by ID."""
    if not exams:
        load_all_data()
    return next((e for e in exams if e.id == id), None)


async def save_exam_resource_file(exam: Exam, uploaded_file) -> dict:
    """Save an exam resource file and return {name, path}."""
    resources_dir = Path("resources") / exam.id
    resources_dir.mkdir(parents=True, exist_ok=True)

    # Save file with original filename
    file_path = resources_dir / uploaded_file.name
    await uploaded_file.save(str(file_path))

    return {"name": uploaded_file.name, "path": str(file_path)}


def delete_submission_files(submission: Submission) -> None:
    """Delete all uploaded files in a submission."""
    for field in submission.data:
        if field.saved_filepath and field.type in (
            FieldType.PDF,
            FieldType.ZIP,
            FieldType.VIDEO,
        ):
            file_path = Path(field.saved_filepath)
            if file_path.exists():
                try:
                    file_path.unlink()
                    print(f"Deleted file: {file_path}")
                except Exception as e:
                    print(f"Error deleting file {file_path}: {e}")


def delete_submission(
    exam: Exam, submission: Submission, delete_files: bool = False
) -> None:
    """Delete a submission from an exam."""
    if delete_files:
        delete_submission_files(submission)

    exam.submissions.remove(submission)
    save_exams()


def delete_all_submissions(exam: Exam, delete_files: bool = False) -> None:
    """Delete all submissions from an exam."""
    if delete_files:
        # Delete entire submissions directory for this exam
        from shutil import rmtree

        dir_name = f"{exam.course.year}-{exam.course.semester}-{exam.course.course_code}-{exam.course.section}--{exam.title}"
        exam_dir = Path("submissions") / dir_name
        if exam_dir.exists():
            try:
                rmtree(exam_dir)
                print(f"Deleted directory: {exam_dir}")
            except Exception as e:
                print(f"Error deleting directory {exam_dir}: {e}")

    # Filter out template submission (student id/name empty) but keep it
    template_submission = next((s for s in exam.submissions if not s.student.id), None)
    exam.submissions.clear()
    if template_submission:
        exam.submissions.append(template_submission)

    save_exams()


def create_submissions_csv(exam: Exam) -> str:
    """Create a CSV file with all submissions data and return its path."""
    # Get actual submissions (exclude template)
    actual_submissions = [s for s in exam.submissions if s.student.id or s.student.name]

    if not actual_submissions:
        return None

    # Create downloads directory if it doesn't exist
    downloads_dir = Path("downloads")
    downloads_dir.mkdir(exist_ok=True)

    # Filename with exam details
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = f"{exam.course.year}-{exam.course.semester}-{exam.course.course_code}-{exam.course.section}--{exam.title}--submissions_{timestamp}.csv"
    csv_path = downloads_dir / csv_filename

    # Prepare CSV headers
    headers = ["Student ID", "Student Name", "Submission ID", "Submission Date"]

    # Add field names as headers
    if actual_submissions and actual_submissions[0].data:
        for field in actual_submissions[0].data:
            headers.append(field.name)

    # Write CSV
    with open(csv_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(headers)

        for submission in actual_submissions:
            row = [
                submission.student.id,
                submission.student.name,
                submission.id,
                submission.submission_date.strftime("%Y-%m-%d %H:%M:%S"),
            ]

            # Add field values
            for field in submission.data:
                if field.type == FieldType.TEXT:
                    row.append(field.value)
                else:  # File types
                    row.append(field.original_filename or field.value)

            writer.writerow(row)

    return str(csv_path)


def create_submissions_zip(exam: Exam) -> str:
    """Create a ZIP file with all uploaded files and return its path."""
    # Get actual submissions (exclude template)
    actual_submissions = [s for s in exam.submissions if s.student.id or s.student.name]

    if not actual_submissions:
        return None

    # Create downloads directory if it doesn't exist
    downloads_dir = Path("downloads")
    downloads_dir.mkdir(exist_ok=True)

    # Filename with exam details
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_filename = f"{exam.course.year}-{exam.course.semester}-{exam.course.course_code}-{exam.course.section}--{exam.title}--files_{timestamp}.zip"
    zip_path = downloads_dir / zip_filename

    # Create ZIP file
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for submission in actual_submissions:
            for field in submission.data:
                if (
                    field.type in (FieldType.PDF, FieldType.ZIP, FieldType.VIDEO)
                    and field.saved_filepath
                ):
                    file_path = Path(field.saved_filepath)
                    if file_path.exists():
                        # Add file to ZIP with relative path
                        arcname = file_path.name
                        zipf.write(file_path, arcname=arcname)

    return str(zip_path)


# Initialize admin passphrase in storage if it doesn't exist
if "admin_passphrase" not in app.storage.general:
    app.storage.general["admin_passphrase"] = "admin"


@ui.page("/admin")
def create_admin_panel():
    """Create the main admin panel with authentication."""
    # Check if user is authenticated
    if not app.storage.user.get("admin_authenticated", False):
        render_login_page()
        return

    # Load data from storage on first load
    load_all_data()

    with ui.column().classes("w-full gap-4 p-4"):
        # Header with logout button
        with ui.row().classes("items-center justify-between mb-4"):
            ui.label("Admin Panel").classes("text-3xl font-bold")
            ui.button(
                "Logout",
                icon="logout",
                color="negative",
                on_click=lambda: (
                    app.storage.user.update({"admin_authenticated": False}),
                    ui.navigate.reload(),
                ),
            )

        ui.separator()
        render_courses_panel()
        render_exams_panel()


def render_login_page():
    """Render the admin login page."""
    with ui.column().classes("w-64 sm:w-80 mx-auto mt-20"):
        ui.label("Admin Login").classes("text-2xl font-bold mb-4")

        passphrase_input = ui.input(
            "Passphrase", password=True, password_toggle_button=True
        ).classes("w-full")

        message = ui.label().classes("mt-4")

        def check_passphrase():
            entered = passphrase_input.value
            stored = app.storage.general.get("admin_passphrase", "admin")
            if entered == stored:
                message.text = "✓ Login successful."
                message.classes(add="text-green-600")
                app.storage.user["admin_authenticated"] = True
                ui.navigate.reload()
            else:
                message.text = "✗ Incorrect passphrase!"
                message.classes(add="text-red-600")
                passphrase_input.value = ""

        ui.button("Login", on_click=check_passphrase).classes("w-full")
        passphrase_input.on("keydown.enter", check_passphrase)


@ui.refreshable
def render_courses_panel():
    """Render the courses management panel."""
    with ui.column().classes("w-full gap-4"):
        # Header
        with ui.row().classes("items-center justify-between"):
            ui.label("Manage Courses").classes("text-2xl font-bold")
            ui.button(
                "Add Course", icon="add", color="primary", on_click=show_add_course_form
            )

        ui.separator()

        # Course cards
        if courses:
            with ui.grid(columns="repeat(auto-fill, minmax(350px, 1fr))").classes(
                "w-full gap-4"
            ):
                for course in reversed(courses):
                    course.render_ui(on_edit=show_edit_course_form)
        else:
            ui.label("No courses found. Click 'Add Course' to create one.").classes(
                "text-gray-400 text-center py-8"
            )


async def show_add_course_form():
    """Show dialog for adding a new course."""
    dialog = ui.dialog()

    with dialog, ui.card().classes("w-full max-w-2xl"):
        ui.label("Add New Course").classes("text-2xl font-bold mb-4")

        # Form fields
        course_code = ui.input(label="Course Code", placeholder="e.g., CSE213").classes(
            "w-full"
        )
        section = ui.number(label="Section", value=1, min=1, max=10).classes("w-full")
        semester = ui.select(
            ["Spring", "Summer", "Autumn"], label="Semester", value="Summer"
        ).classes("w-full")
        year = ui.number(label="Year", value=2025, min=2000, max=2100).classes("w-full")

        ui.label("Student List").classes("font-semibold mt-4")
        students_textarea = (
            ui.textarea(
                placeholder="Enter student IDs and names, one per line (copy from excel):\n2245678\tAsif\n2345678\tMahmood"
            )
            .classes("w-full")
            .props("clearable")
        )

        # Buttons
        with ui.row().classes("gap-2 justify-end mt-4"):
            ui.button("Cancel", on_click=dialog.close).props("outline")

            def save_course():
                if (
                    not course_code.value
                    or not section.value
                    or not semester.value
                    or not year.value
                ):
                    ui.notify("Please fill in all required fields", type="negative")
                    return

                # Parse student list
                student_list = []
                if students_textarea.value:
                    for line in students_textarea.value.splitlines():
                        if line.strip():
                            parts = line.split("\t")
                            if len(parts) >= 2:
                                student_id = parts[0].strip()
                                student_name = parts[1].strip()
                                student_list.append(
                                    Student(id=student_id, name=student_name)
                                )

                # Create and add course
                new_course = Course(
                    course_code=course_code.value,
                    section=int(section.value),
                    semester=semester.value,
                    year=int(year.value),
                    student_list=student_list,
                )
                courses.append(new_course)
                save_courses()

                ui.notify(f"Course {new_course} added successfully")
                dialog.submit(True)

            ui.button("Save", on_click=save_course, color="primary")

        if await dialog:
            render_courses_panel.refresh()


async def show_edit_course_form(course: Course):
    """Show dialog for editing an existing course."""
    dialog = ui.dialog()

    with dialog, ui.card().classes("w-full max-w-2xl"):
        ui.label("Edit Course").classes("text-2xl font-bold mb-4")

        # Form fields with pre-filled values
        course_code = ui.input(label="Course Code", placeholder="e.g., CSE213").classes(
            "w-full"
        )
        course_code.set_value(course.course_code)

        section = ui.number(
            label="Section", value=course.section, min=1, max=10
        ).classes("w-full")

        semester = ui.select(
            ["Spring", "Summer", "Autumn"], label="Semester", value=course.semester
        ).classes("w-full")

        year = ui.number(label="Year", value=course.year, min=2000, max=2100).classes(
            "w-full"
        )

        ui.label("Student List").classes("font-semibold mt-4")
        students_textarea = (
            ui.textarea(
                placeholder="Enter student IDs and names, one per line (copy from excel):\n2245678\tAsif\n2345678\tMahmood"
            )
            .classes("w-full")
            .props("clearable")
        )

        # Pre-fill student list
        student_list_text = "\n".join(
            f"{student.id}\t{student.name}" for student in course.student_list
        )
        students_textarea.set_value(student_list_text)

        # Buttons
        with ui.row().classes("gap-2 justify-end mt-4"):
            ui.button("Cancel", on_click=dialog.close).props("outline")

            def save_course():
                if (
                    not course_code.value
                    or not section.value
                    or not semester.value
                    or not year.value
                ):
                    ui.notify("Please fill in all required fields", type="negative")
                    return

                # Parse student list
                student_list = []
                if students_textarea.value:
                    for line in students_textarea.value.splitlines():
                        if line.strip():
                            parts = line.split("\t")
                            if len(parts) >= 2:
                                student_id = parts[0].strip()
                                student_name = parts[1].strip()
                                student_list.append(
                                    Student(id=student_id, name=student_name)
                                )

                # Update course
                course.course_code = course_code.value
                course.section = int(section.value)
                course.semester = semester.value
                course.year = int(year.value)
                course.student_list = student_list

                save_courses()

                ui.notify(f"Course {course} updated successfully")
                dialog.submit(True)

            ui.button("Save", on_click=save_course, color="primary")

        if await dialog:
            render_courses_panel.refresh()


@ui.refreshable
def render_exams_panel():
    """Render the exams management panel."""
    with ui.column().classes("w-full gap-4 mt-5"):
        # Header
        with ui.row().classes("items-center justify-between"):
            ui.label("Manage Exams").classes("text-2xl font-bold")
            ui.button(
                "Add Exam", icon="add", color="primary", on_click=show_add_exam_form
            )

        ui.separator()

        # Exam list
        if exams:
            with ui.grid(columns="repeat(auto-fill, minmax(350px, 1fr))").classes(
                "w-full gap-4"
            ):
                for exam in reversed(exams):
                    exam.render_ui()
        else:
            ui.label("No exams found. Click 'Add Exam' to create one.").classes(
                "text-gray-400 text-center py-8"
            )


async def show_add_exam_form():
    """Show dialog for adding a new exam."""
    dialog = ui.dialog()

    with dialog, ui.card().classes("w-full max-w-2xl"):
        ui.label("Add New Exam").classes("text-2xl font-bold mb-4")

        # Form fields
        title = ui.input(label="Exam Title", placeholder="e.g., Quiz 1").classes(
            "w-full"
        )

        # Course dropdown
        course_options = {course: str(course) for course in reversed(courses)}
        if not course_options:
            ui.label("No courses available. Please create a course first.").classes(
                "text-orange-600"
            )
            course_select = None
        else:
            course_select = ui.select(
                course_options,
                label="Course",
                value=list(course_options.keys())[0] if course_options else None,
            ).classes("w-full")

        # Dynamic fields section
        ui.label("Submission Fields").classes("font-semibold mt-6 mb-2")
        ui.label("Define what fields students need to submit").classes(
            "text-sm text-gray-600 mb-4"
        )

        fields_data = {"fields": []}

        fields_container = ui.column().classes(
            "w-full gap-3 border rounded p-3 bg-gray-50"
        )

        def add_field():
            """Add a new field input row."""
            field_index = len(fields_data["fields"])

            with fields_container, ui.row().classes("w-full items-end gap-2"):
                field_name = ui.input(
                    label="Field Name", placeholder="e.g., Project Report"
                ).classes("flex-grow")

                field_type = ui.select(
                    ["text", "pdf", "zip", "video"], label="Type", value="text"
                ).classes("w-32")

                def remove_field(idx):
                    def on_remove():
                        fields_data["fields"].pop(idx)
                        fields_container.update()

                    return on_remove

                ui.button(
                    icon="delete", on_click=remove_field(field_index), color="negative"
                ).props("flat")

                fields_data["fields"].append(
                    {
                        "name_input": field_name,
                        "type_select": field_type,
                    }
                )

        # Add initial field
        add_field()

        # Add field button
        ui.button("Add Field", icon="add", on_click=add_field).classes("w-full mt-2")

        # Resource Files Section
        ui.separator()
        ui.label("Resource Files (Optional)").classes("font-semibold mt-6 mb-2")
        ui.label("Upload files for students to download").classes(
            "text-sm text-gray-600 mb-4"
        )

        resource_files_data = {"files": []}
        resource_files_list = ui.column().classes("w-full gap-2")

        async def on_resource_upload(e):
            """Handle resource file upload."""
            try:
                # Exam hasn't been created yet, so store files temporarily
                resource_files_data["files"].append(
                    {"name": e.file.name, "file": e.file}
                )

                # Update the display
                with resource_files_list:
                    ui.label(f"✓ {e.file.name}").classes("text-sm text-green-600")

                ui.notify(f"File added: {e.file.name}", type="positive")
            except Exception as ex:
                ui.notify(f"Error adding file: {str(ex)}", type="negative")

        ui.upload(
            label="Upload Resource Files",
            on_upload=on_resource_upload,
            auto_upload=True,
        ).classes("w-full").props('accept="*"')

        # Buttons
        with ui.row().classes("gap-2 justify-end mt-6"):
            ui.button("Cancel", on_click=dialog.close).props("outline")

            async def save_exam():
                if not title.value:
                    ui.notify("Please enter an exam title", type="negative")
                    return

                if not course_select or not course_select.value:
                    ui.notify("Please select a course", type="negative")
                    return

                # Validate fields
                if not fields_data["fields"]:
                    ui.notify("Please add at least one field", type="negative")
                    return

                field_names = set()
                for field_info in fields_data["fields"]:
                    field_name = field_info["name_input"].value.strip()
                    if not field_name:
                        ui.notify("All fields must have a name", type="negative")
                        return
                    if field_name in field_names:
                        ui.notify(
                            f"Duplicate field name: {field_name}", type="negative"
                        )
                        return
                    field_names.add(field_name)

                # Get selected course
                selected_course = course_select.value

                # Create fields list
                exam_fields = []
                for field_info in fields_data["fields"]:
                    field_name = field_info["name_input"].value.strip()
                    field_type = FieldType[field_info["type_select"].value.upper()]
                    exam_fields.append(Field(name=field_name, type=field_type))

                # Create and add exam
                new_exam = Exam(
                    title=title.value,
                    course=selected_course,
                )

                # Create a default submission with the fields for reference
                if exam_fields:
                    default_submission = Submission(
                        exam=new_exam, student=Student(id="", name=""), data=exam_fields
                    )
                    new_exam.submissions.append(default_submission)

                exams.append(new_exam)
                save_exams()

                # Save resource files if any
                for file_info in resource_files_data["files"]:
                    try:
                        saved_file = await save_exam_resource_file(
                            new_exam, file_info["file"]
                        )
                        new_exam.resource_files.append(saved_file)
                    except Exception as ex:
                        print(f"Error saving resource file: {ex}")

                save_exams()

                ui.notify(
                    f"Exam '{title.value}' added successfully with {len(exam_fields)} fields"
                )
                dialog.submit(True)

            if course_select:
                ui.button("Save", on_click=save_exam, color="primary")

        if await dialog:
            render_exams_panel.refresh()


@ui.page("/admin/exams/{exam_id}")
def exam_management_page(exam_id: str):
    """Manage a specific exam."""
    # Check if user is authenticated
    if not app.storage.user.get("admin_authenticated", False):
        ui.label("Access Denied. Please login first.").classes("text-red-600 p-4")
        ui.button(
            "Go to Login", icon="arrow_back", on_click=lambda: ui.navigate.to("/admin")
        )
        return

    # Load data if not already loaded
    if not courses or not exams:
        load_all_data()

    # Find the exam
    exam = next((e for e in exams if e.id == exam_id), None)
    if not exam:
        ui.label(f"Exam {exam_id} not found").classes("text-red-600 p-4")
        return

    with ui.column().classes("w-full gap-4 p-4"):
        # Header
        with ui.row().classes("items-center justify-between"):
            ui.label(f"Manage: {exam.title}").classes("text-2xl font-bold")
            ui.button(
                "Back", icon="arrow_back", on_click=lambda: ui.navigate.to("/admin")
            )

        ui.separator()

        # Exam Info
        with ui.card().classes("w-full"):
            ui.label("Exam Information").classes("text-lg font-bold mb-2")
            ui.label(f"ID: {exam.id}").classes("text-sm text-gray-600")
            ui.label(
                f"Course: {exam.course.course_code} - Section {exam.course.section}"
            ).classes("text-sm text-gray-600")
            ui.label(f"Status: {exam.get_status().value}").classes(
                "text-sm text-gray-600"
            )
            ui.label(f"Submissions: {len(exam.submissions)}").classes(
                "text-sm text-gray-600"
            )

        # Accept Submissions Control
        with ui.card().classes("w-full"):
            with ui.row().classes("items-center justify-between"):
                ui.label("Accept Submissions").classes("text-lg font-bold")

                def toggle_accepting(e):
                    exam.is_accepting = e.value
                    save_exams()
                    status_text = "🟢 Accepting" if e.value else "🔴 Stopped"
                    ui.notify(f"Accepting submissions: {status_text}")

                switch = ui.switch(value=exam.is_accepting, on_change=toggle_accepting)
                switch.classes("ml-auto")

        ui.separator()

        # Student Status Section
        with ui.card().classes("w-full"):
            ui.label("Student Status").classes("text-lg font-bold mb-4")

            if exam.course.student_list:
                with ui.grid(columns="repeat(auto-fill, minmax(250px, 1fr))").classes(
                    "w-full gap-3"
                ):
                    for student in exam.course.student_list:
                        # Check student status
                        submission = next(
                            (s for s in exam.submissions if s.student.id == student.id),
                            None,
                        )

                        # Determine status and color
                        if (
                            submission and submission.student.id
                        ):  # Has completed submission
                            status = "✓ Submitted"
                            status_color = "bg-green-100 border-l-4 border-green-500"
                            timestamp = submission.submission_date.strftime(
                                "%Y-%m-%d %H:%M"
                            )
                        else:
                            status = "Not Yet Submitted"
                            status_color = "bg-gray-100 border-l-4 border-gray-400"
                            timestamp = ""

                        # Student card - clickable
                        def on_click_card(sid=student.id):
                            """Scroll to submission details for this student."""
                            ui.run_javascript(f"""
                                const element = document.querySelector('[data-submission-id="{sid}"]');
                                if (element) {{
                                    element.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                                }}
                            """)

                        with (
                            ui.card()
                            .classes(
                                f"w-full {status_color} cursor-pointer hover:shadow-lg transition-shadow"
                            )
                            .on("click", on_click_card)
                        ):
                            with ui.row().classes("items-center justify-between"):
                                with ui.column().classes("flex-grow"):
                                    ui.label(student.name).classes(
                                        "font-semibold text-base"
                                    )
                                    ui.label(f"ID: {student.id}").classes(
                                        "text-sm text-gray-600"
                                    )
                                    if timestamp:
                                        ui.label(f"Submitted: {timestamp}").classes(
                                            "text-xs text-gray-500 mt-1"
                                        )

                                ui.label(status).classes("text-sm font-medium")
            else:
                ui.label("No students in this course").classes("text-gray-400")

        ui.separator()

        # Submissions section
        with ui.card().classes("w-full"):
            with ui.row().classes("items-center justify-between mb-4"):
                ui.label(
                    f"Submissions ({len([s for s in exam.submissions if s.student.id])})"
                ).classes("text-lg font-bold")

                with ui.row().classes("gap-2"):

                    async def download_csv():
                        csv_path = await run.io_bound(create_submissions_csv, exam)
                        if csv_path:
                            ui.download(csv_path)
                            ui.notify(
                                f"CSV downloaded: {Path(csv_path).name}",
                                type="positive",
                            )
                        else:
                            ui.notify("No submissions to download", type="warning")

                    async def download_zip():
                        zip_path = await run.io_bound(create_submissions_zip, exam)
                        if zip_path:
                            ui.download(zip_path)
                            ui.notify(
                                f"ZIP downloaded: {Path(zip_path).name}",
                                type="positive",
                            )
                        else:
                            ui.notify("No files to download", type="warning")

                    ui.button(
                        "Download CSV",
                        icon="download",
                        color="primary",
                        on_click=download_csv,
                    ).props("outline")

                    ui.button(
                        "Download ZIP",
                        icon="download",
                        color="primary",
                        on_click=download_zip,
                    ).props("outline")

                async def show_reset_confirmation():
                    """Show confirmation dialog for resetting all submissions."""
                    dialog = ui.dialog()
                    with dialog, ui.card().classes("w-full max-w-md"):
                        ui.label("Reset All Submissions?").classes(
                            "text-lg font-bold mb-4"
                        )
                        ui.label(
                            "This will delete all submissions for this exam."
                        ).classes("text-sm text-gray-600 mb-4")

                        delete_files_checkbox = ui.checkbox(
                            "Also delete uploaded files from disk"
                        )

                        with ui.row().classes("gap-2 justify-end mt-6"):
                            ui.button("Cancel", on_click=dialog.close).props("outline")

                            async def confirm_reset():
                                await run.io_bound(
                                    delete_all_submissions,
                                    exam,
                                    delete_files_checkbox.value,
                                )
                                ui.notify(
                                    "All submissions deleted successfully",
                                    type="positive",
                                )
                                ui.navigate.reload()

                            ui.button(
                                "Delete All", on_click=confirm_reset, color="negative"
                            )

                    if await dialog:
                        pass

                ui.button(
                    "Reset All",
                    icon="delete_sweep",
                    color="negative",
                    on_click=show_reset_confirmation,
                ).props("outline")

            if exam.submissions:
                # Filter out the default submission (student id and name are empty)
                actual_submissions = [
                    s for s in exam.submissions if s.student.id or s.student.name
                ]

                if actual_submissions:
                    with ui.column().classes("w-full gap-3"):
                        for submission in actual_submissions:
                            with (
                                ui.card()
                                .props(f"data-submission-id={submission.student.id}")
                                .classes("w-full")
                            ):
                                # Header with delete button
                                with ui.row().classes(
                                    "items-center justify-between mb-2"
                                ):
                                    ui.label(
                                        f"{submission.student.name} ({submission.student.id})"
                                    ).classes("text-lg font-bold")

                                    async def show_delete_confirmation(sub=submission):
                                        """Show confirmation dialog for deleting a submission."""
                                        dialog = ui.dialog()
                                        with (
                                            dialog,
                                            ui.card().classes("w-full max-w-md"),
                                        ):
                                            ui.label("Delete Submission?").classes(
                                                "text-lg font-bold mb-4"
                                            )
                                            ui.label(
                                                f"Delete submission from {sub.student.name}?"
                                            ).classes("text-sm text-gray-600 mb-4")

                                            delete_files_checkbox = ui.checkbox(
                                                "Also delete uploaded files from disk"
                                            )

                                            with ui.row().classes(
                                                "gap-2 justify-end mt-6"
                                            ):
                                                ui.button(
                                                    "Cancel", on_click=dialog.close
                                                ).props("outline")

                                                async def confirm_delete():
                                                    await run.io_bound(
                                                        delete_submission,
                                                        exam,
                                                        sub,
                                                        delete_files_checkbox.value,
                                                    )
                                                    ui.notify(
                                                        f"Submission from {sub.student.name} deleted",
                                                        type="positive",
                                                    )
                                                    ui.navigate.reload()

                                                ui.button(
                                                    "Delete",
                                                    on_click=confirm_delete,
                                                    color="negative",
                                                )

                                        if await dialog:
                                            pass

                                    ui.button(
                                        icon="delete",
                                        on_click=show_delete_confirmation,
                                        color="negative",
                                    ).props("flat")

                                ui.label(f"ID: {submission.id}").classes(
                                    "text-xs text-gray-500"
                                )
                                ui.label(
                                    f"Date: {submission.submission_date.strftime('%Y-%m-%d %H:%M')}"
                                ).classes("text-xs text-gray-600")

                                ui.separator()

                                # Submission data
                                if submission.data:
                                    for field in submission.data:
                                        with ui.row().classes(
                                            "w-full items-center p-2"
                                        ):
                                            ui.label(f"{field.name}:").classes(
                                                "w-32 font-semibold"
                                            )
                                            if field.type in (
                                                FieldType.PDF,
                                                FieldType.ZIP,
                                                FieldType.VIDEO,
                                            ):
                                                file_icons = {
                                                    FieldType.PDF: "📄",
                                                    FieldType.ZIP: "📦",
                                                    FieldType.VIDEO: "🎬",
                                                }
                                                icon = file_icons.get(field.type, "📄")
                                                with ui.column().classes(
                                                    "text-sm text-blue-600 flex-grow"
                                                ):
                                                    if field.original_filename:
                                                        ui.label(
                                                            f"{icon} {field.original_filename}"
                                                        ).classes("text-sm")
                                                        ui.label(
                                                            f"Saved: {field.saved_filepath}"
                                                        ).classes(
                                                            "text-xs text-gray-500"
                                                        )
                                                    else:
                                                        ui.label(
                                                            f"{icon} {field.value}"
                                                        ).classes("text-sm")

                                                # Add play button for videos
                                                if (
                                                    field.type == FieldType.VIDEO
                                                    and field.saved_filepath
                                                ):

                                                    async def show_video_player(
                                                        video_path=field.saved_filepath,
                                                        video_name=field.original_filename,
                                                    ):
                                                        """Show video player dialog."""
                                                        dialog = ui.dialog()
                                                        with (
                                                            dialog,
                                                            ui.card().classes(
                                                                "w-full max-w-4xl"
                                                            ),
                                                        ):
                                                            ui.label(
                                                                f"Playing: {video_name}"
                                                            ).classes(
                                                                "text-lg font-bold mb-4"
                                                            )

                                                            # Use ui.video for video playback
                                                            ui.video(
                                                                video_path
                                                            ).classes("w-full")

                                                            with ui.row().classes(
                                                                "gap-2 justify-end mt-4"
                                                            ):
                                                                ui.button(
                                                                    "Close",
                                                                    on_click=dialog.close,
                                                                    color="primary",
                                                                )

                                                        if await dialog:
                                                            pass

                                                    ui.button(
                                                        icon="play_circle",
                                                        on_click=show_video_player,
                                                        color="primary",
                                                    ).props("flat no-caps").classes(
                                                        "ml-2"
                                                    )
                                            else:
                                                ui.label(field.value).classes("text-sm")
                                else:
                                    ui.label("No data submitted").classes(
                                        "text-gray-400"
                                    )
                else:
                    ui.label("No student submissions yet").classes("text-gray-400")
            else:
                ui.label("No submissions").classes("text-gray-400")


if __name__ == "__main__":
    ui.run(storage_secret="some random secret that is really hard to guess")
