"""
Data models for the Exam Uploader with NiceGUI UI rendering.
Each model includes a method to render its UI components.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from nicegui import app, ui

ALLOWED_EXTENSIONS = {".pdf", ".zip", ".mp4", ".avi", ".mov", ".mkv"}


# Initialize ID counters in app.storage if they don't exist
def _init_id_counters():
    """Initialize ID counters in app.storage for persistent IDs."""
    if "course_id_counter" not in app.storage.general:
        app.storage.general["course_id_counter"] = 1000
    if "exam_id_counter" not in app.storage.general:
        app.storage.general["exam_id_counter"] = 2000
    if "submission_id_counter" not in app.storage.general:
        app.storage.general["submission_id_counter"] = 3000


def _get_next_course_id() -> str:
    """Get the next auto-increment course ID."""
    _init_id_counters()
    course_id = app.storage.general["course_id_counter"]
    app.storage.general["course_id_counter"] += 1
    return f"C{course_id}"


def _get_next_exam_id() -> str:
    """Get the next auto-increment exam ID."""
    _init_id_counters()
    exam_id = app.storage.general["exam_id_counter"]
    app.storage.general["exam_id_counter"] += 1
    return f"E{exam_id}"


def _get_next_submission_id() -> str:
    """Get the next auto-increment submission ID."""
    _init_id_counters()
    submission_id = app.storage.general["submission_id_counter"]
    app.storage.general["submission_id_counter"] += 1
    return f"S{submission_id}"


class FieldType(str, Enum):
    """Field types for submission data."""

    TEXT = "text"
    PDF = "pdf"
    ZIP = "zip"
    VIDEO = "video"

    @staticmethod
    def get_file_extensions(field_type: "FieldType") -> list[str]:
        """Get allowed file extensions for a field type."""
        extensions = {
            FieldType.PDF: [".pdf"],
            FieldType.ZIP: [".zip"],
            # FieldType.VIDEO: [".mp4", ".avi", ".mov", ".mkv", ".webm"],
            FieldType.VIDEO: ["video/*"],
        }
        return extensions.get(field_type, [])


class ExamStatus(str, Enum):
    """Status of an exam based on current time."""

    UPCOMING = "upcoming"
    RUNNING = "running"
    COMPLETED = "completed"


@dataclass
class Field:
    """Represents a field in a submission form."""

    name: str
    type: FieldType
    value: str = ""  # text value or file path
    original_filename: str = ""  # Only for file uploads
    saved_filepath: str = ""  # Only for file uploads (relative path)

    def render_ui(self):
        """Render field in the UI as input control."""
        if self.type == FieldType.TEXT:
            return ui.input(
                label=self.name,
                placeholder=f"Enter {self.name.lower()}",
                value=self.value,
            ).classes("w-full")
        else:  # PDF, ZIP, or VIDEO
            extensions = FieldType.get_file_extensions(self.type)
            return (
                ui.upload(label=self.name, auto_upload=True)
                .props(f'accept="{" ".join(extensions)}"')
                .classes("w-full")
            )


@dataclass
class Student:
    """Represents a student in the system."""

    id: str
    name: str
    submissions: list["Submission"] = field(default_factory=list)

    def render_ui(self):
        """Render student information in the UI."""
        with ui.card().classes("w-full"):
            ui.label(self.name).classes("text-lg font-bold")
            ui.label(f"ID: {self.id}").classes("text-sm text-gray-600")
            ui.label(f"Submissions: {len(self.submissions)}").classes(
                "text-sm text-gray-600 mt-2"
            )

    def __str__(self) -> str:
        return f"{self.id} - {self.name}"

    def __hash__(self) -> int:
        return self.id.__hash__()


@dataclass
class Course:
    """Represents a course."""

    course_code: str
    section: int
    semester: str
    year: int
    student_list: list[Student] = field(default_factory=list)
    id: str = field(default_factory=_get_next_course_id)

    def render_ui(self, on_edit=None):
        """Render course information in the UI."""
        with ui.card().classes("w-full"):
            with ui.row().classes("items-center justify-between"):
                with ui.column().classes("flex-grow"):
                    ui.label(f"{self.course_code} - Section {self.section}").classes(
                        "text-lg font-bold"
                    )
                    ui.label(f"{self.semester} {self.year}").classes("")
                    ui.label(f"Students: {len(self.student_list)}").classes("mt-2")
                    ui.label(f"ID: {self.id}").classes("text-xs text-gray-500 mt-2")

            # Action buttons
            if on_edit:
                ui.button("Edit", icon="edit", on_click=lambda: on_edit(self)).props(
                    "flat"
                ).classes("w-full mt-4")

    def __str__(self) -> str:
        return f"{self.year}-{self.semester}-{self.course_code}-{self.section} ({len(self.student_list)})"

    def __hash__(self) -> int:
        return self.id.__hash__()


@dataclass
class Submission:
    """Represents a student's submission for an exam."""

    exam: "Exam"
    student: Student
    submission_date: datetime = field(default_factory=datetime.now)
    data: list[Field] = field(default_factory=list)
    id: str = field(default_factory=_get_next_submission_id)

    def render_ui(self):
        """Render submission details in the UI."""
        with ui.card().classes("w-full"):
            with ui.row().classes("items-center justify-between"):
                ui.label(f"{self.student.name} ({self.student.id})").classes(
                    "text-lg font-bold"
                )
                ui.label(f"ID: {self.id}").classes("text-xs text-gray-500")

            ui.separator()

            if self.data:
                for field in self.data:
                    with ui.row().classes("w-full items-center p-2"):
                        ui.label(f"{field.name}:").classes("w-32 font-semibold")
                        if field.type in (
                            FieldType.PDF,
                            FieldType.ZIP,
                            FieldType.VIDEO,
                        ):
                            # File upload types
                            file_icons = {
                                FieldType.PDF: "📄",
                                FieldType.ZIP: "📦",
                                FieldType.VIDEO: "🎬",
                            }
                            icon = file_icons.get(field.type, "📄")
                            with ui.column().classes("text-sm text-blue-600"):
                                if field.original_filename:
                                    ui.label(
                                        f"{icon} {field.original_filename}"
                                    ).classes("text-sm")
                                    ui.label(f"Saved: {field.saved_filepath}").classes(
                                        "text-xs text-gray-500"
                                    )
                                else:
                                    ui.label(f"{icon} {field.value}").classes("text-sm")
                        else:
                            ui.label(field.value).classes("text-sm")
            else:
                ui.label("No data submitted").classes("text-gray-400")


@dataclass
class Exam:
    """Represents an exam."""

    title: str
    course: Course
    submissions: list[Submission] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    id: str = field(default_factory=_get_next_exam_id)
    is_accepting: bool = True
    resource_files: list[dict] = field(default_factory=list)  # [{name, path}, ...]

    def get_status(self) -> ExamStatus:
        """Get the current status of the exam."""
        now = datetime.now()
        if now < self.start_time:
            return ExamStatus.UPCOMING
        elif self.end_time is None or now < self.end_time:
            return ExamStatus.RUNNING
        else:
            return ExamStatus.COMPLETED

    def get_status_color(self) -> str:
        """Get color for status badge."""
        status = self.get_status()
        colors = {
            ExamStatus.UPCOMING: "blue",
            ExamStatus.RUNNING: "green",
            ExamStatus.COMPLETED: "gray",
        }
        return colors[status]

    def render_ui(self):
        """Render exam details in the UI."""
        with ui.card().classes("w-full"):
            with ui.row().classes("items-center justify-between"):
                ui.label(self.title).classes("text-xl font-bold")
                ui.label(f"ID: {self.id}").classes("text-xs text-gray-500")

            ui.label(f"{self.course}").classes("text-sm text-gray-600")
            ui.label(f"Submissions: {len(self.submissions)}").classes(
                "text-sm text-gray-600 mt-2"
            )

            # Manage button
            ui.button(
                "Manage",
                icon="settings",
                on_click=lambda: ui.navigate.to(f"/admin/exams/{self.id}"),
            ).props("outline").classes("w-full mt-4")

    def render_sidebar_item(self):
        """Render exam item for left sidebar with color coding."""
        status = self.get_status()
        status_colors = {
            ExamStatus.UPCOMING: "bg-blue-100 border-l-4 border-blue-500",
            ExamStatus.RUNNING: "bg-green-100 border-l-4 border-green-500",
            ExamStatus.COMPLETED: "bg-gray-100 border-l-4 border-gray-500",
        }
        status_text = {
            ExamStatus.UPCOMING: "Upcoming",
            ExamStatus.RUNNING: "Running",
            ExamStatus.COMPLETED: "Completed",
        }

        with ui.row().classes(
            f"w-full p-3 rounded cursor-pointer hover:shadow-md {status_colors[status]}"
        ):
            with ui.column().classes("flex-grow"):
                ui.label(self.title).classes("font-semibold text-sm")
                ui.label(f"{self.course.course_code}").classes("text-xs text-gray-600")
            ui.badge(status_text[status]).classes("text-xs")

    def render_submission_form(self):
        """Render form for student submission."""
        with ui.card().classes("w-full max-w-2xl"):
            ui.label(f"Submit to {self.title}").classes("text-2xl font-bold mb-4")
            ui.label(
                f"{self.course.course_code} - Section {self.course.section}"
            ).classes("text-sm text-gray-600 mb-6")

            # Student info
            student_id_input = ui.input(label="Student ID").classes("w-full")
            student_name_input = ui.input(label="Student Name").classes("w-full")

            # Dynamic fields
            form_fields = {}
            for i, field in enumerate(
                self.submissions[0].data if self.submissions else []
            ):
                form_fields[field.name] = field.render_ui()

            # Submit button
            status_label = ui.label().classes("mt-4")

            def handle_submit():
                if not student_id_input.value or not student_name_input.value:
                    status_label.set_text("Please fill in all required fields")
                    status_label.classes(add="text-red-600")
                    return

                # Create student and submission
                student = Student(
                    id=student_id_input.value, name=student_name_input.value
                )

                # Collect field data
                submission_fields = [
                    Field(name=field.name, type=field.type, value=field.value)
                    for field in (self.submissions[0].data if self.submissions else [])
                ]

                submission = Submission(
                    exam=self, student=student, data=submission_fields
                )
                self.submissions.append(submission)

                status_label.set_text(
                    f"✓ Submission received from {student_name_input.value}"
                )
                status_label.classes(add="text-green-600")

            ui.button("Submit", on_click=handle_submit).classes("w-full mt-4")

    def render_submissions_list(self):
        """Render list of all submissions for this exam."""
        with ui.column().classes("w-full"):
            ui.label(f"{self.title} - Submissions ({len(self.submissions)})").classes(
                "text-xl font-bold mb-4"
            )

            if not self.submissions:
                ui.label("No submissions yet").classes("text-gray-400 py-8")
            else:
                for submission in self.submissions:
                    submission.render_ui()
                    ui.separator()
