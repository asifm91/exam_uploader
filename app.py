from nicegui import ui, app, Client
import datetime
import os
from pathlib import Path

if "course_code" not in app.storage.general:
    app.storage.general["course_code"] = "CSE213"
if "section" not in app.storage.general:
    app.storage.general["section"] = 1
if "submissions" not in app.storage.general:
    app.storage.general["submissions"] = []


@ui.page("/_admin")
def admin_page():
    # log in
    if not app.storage.user.get("authenticated", False):
        with ui.column().classes("w-64 sm:w-80 mx-auto mt-10"):
            ui.label("Admin Login").classes("text-2xl font-bold mb-4")
            password_input = ui.input(
                "Password", password=True, password_toggle_button=True
            ).classes("w-full")
            message = ui.label()

            def check_password():
                entered = password_input.value
                stored = app.storage.general.get("password", "admin")
                if entered == stored:
                    message.text = "Login successful."
                    app.storage.user["authenticated"] = True
                    ui.navigate.reload()
                else:
                    message.text = "Incorrect password!"

            ui.button("Login", on_click=check_password).classes("w-full")
            password_input.on("keydown.enter", check_password)

        return

    # admin panel
    ## log out and password change
    with ui.column():
        ui.button(
            "Logout",
            icon="logout",
            on_click=lambda: (
                app.storage.user.update({"authenticated": False}),
                ui.navigate.reload(),
            ),
        ).props("outline color=negative")
        # password_change_input = ui.input(
        #     "Update Password", password=True, password_toggle_button=True
        # ).classes("w-full")
        # password_change_label = ui.label("")
        # if app.storage.general.get("password", "admin") == "admin":
        #     password_change_label.set_text(
        #         "Default password is in use! Please change your password."
        #     )
        # password_change_input.on(
        #     "keydown.enter",
        #     lambda e: (
        #         app.storage.general.update({"password": password_change_input.value}),
        #         password_change_label.set_text("Password updated successfully."),
        #     ),
        # )

    ui.separator()

    with ui.grid(columns="auto 1fr").classes("gap-4"):
        dialog = ui.dialog()

        async def show_delete_all_confirmation():
            dialog.clear()
            with dialog, ui.card().classes("w-96 h-32 p-4 justify-between"):
                ui.label("Are you sure you want to delete all submissions?")
                with ui.row().classes("w-full justify-end"):
                    ui.button("Yes", on_click=lambda: dialog.submit(True)).props(
                        "color=negative"
                    )
                    ui.button(
                        "Cancel", on_click=lambda: dialog.submit(False)
                    ).props("outline")

            confirmed = await dialog
            if confirmed:
                app.storage.general["submissions"].clear()
                app.storage.client.get("selected_submissions", []).clear()
                ui.notify("All submissions deleted successfully.")
                generate_submissions_table.refresh()
                display_submission_details.refresh()

        async def show_delete_confirmation(submission_info):
            dialog.clear()
            with dialog, ui.card().classes("w-96 h-32 p-4 justify-between"):
                ui.label("Are you sure you want to delete the submission?")
                with ui.row().classes("w-full justify-end"):
                    ui.button("Yes", on_click=lambda: dialog.submit(True)).props(
                        "color=negative"
                    )
                    ui.button(
                        "Cancel", on_click=lambda: dialog.submit(False)
                    ).props("outline")

            confirmed = await dialog
            if confirmed:
                app.storage.general["submissions"].remove(submission_info)
                app.storage.client.get("selected_submissions", []).clear()
                ui.notify("Submission deleted successfully.")
                generate_submissions_table.refresh()
                display_submission_details.refresh()

        ## course and student information
        with ui.column().classes("w-96"):
            ui.label("Course and Student Information").classes("text-2xl font-bold")

            ui.input(
                "Year",
            ).classes("w-full").bind_value(app.storage.general, "year")
            ui.select(["Spring", "Summer", "Autumn"], label="Semester").classes(
                "w-full"
            ).bind_value(app.storage.general, "semester")
            ui.input("Course Code").classes("w-full").bind_value(
                app.storage.general, "course_code"
            )
            ui.select(list(range(1, 9)), label="Section").classes("w-full").bind_value(
                app.storage.general, "section"
            )
            ui.textarea(
                "Student List",
                placeholder="Enter student IDs and names, one per line (copy from excel): \n2245678\tAsif\n2345678\tMahmood",
            ).classes("w-full").bind_value(
                app.storage.general, "students_list_input"
            ).props("clearable")

            def update_student_info():
                student_list = []
                student_list_input = (
                    app.storage.general.get("students_list_input") or ""
                )
                for line in student_list_input.splitlines():
                    if line.strip():
                        parts = line.split("\t")
                        if len(parts) == 2:
                            student_id, student_name = parts
                            student_list.append(
                                f"{student_id.strip()} - {student_name.strip()}"
                            )

                app.storage.general.update({"students": student_list})
                ui.notify("Student list updated successfully.")

                display_students.refresh()

            ui.button("Update", on_click=update_student_info).classes("w-full")

            @ui.refreshable
            def display_students():
                students = app.storage.general.get("students", [])
                with ui.expansion(f"Student List ({len(students)} students)").classes(
                    "w-full text-lg font-bold"
                ):
                    with ui.list().props("bordered separator dense"):
                        for student in students:
                            ui.item(student).classes("text-sm font-normal")

            display_students()

        ## submission management
        with ui.column():
            ui.label("Submission Management").classes("text-2xl font-bold")

            ui.switch("Accepting responses").props("size=xl").bind_value(
                app.storage.general, "enable_form_submission"
            )

            @ui.refreshable
            def generate_submissions_table():
                submissions = app.storage.general.get("submissions", [])
                ui.label(f"Total Submissions: {len(submissions)}")
                ui.table(
                    columns=[
                        {
                            "name": "student_id",
                            "label": "Student ID",
                            "field": "student_id",
                            "sortable": True,
                        },
                        {
                            "name": "student_name",
                            "label": "Name",
                            "field": "student_name",
                            "headerClasses": "w-80",
                        },
                        {"name": "section", "label": "Section", "field": "section"},
                        {
                            "name": "timestamp",
                            "label": "Submitted At",
                            "field": "timestamp",
                            "headerClasses": "w-64",
                            "sortable": True,
                        },
                        {
                            "name": "ip",
                            "label": "IP Address",
                            "field": "ip",
                            "headerClasses": "w-40",
                        },
                    ],
                    rows=submissions,
                    row_key="s_filename",
                    column_defaults={"align": "center"},
                    on_select=lambda e: (
                        app.storage.client.update({"selected_submissions": e.selection}),
                        display_submission_details.refresh(),
                    ),
                ).props("").set_selection("single")

                with ui.row():
                    ui.button(
                        "Export CSV",
                        on_click=lambda: (
                            ui.download.content(
                                "Timestamp,ID,Name,Section,Original Filename,Saved Filename,IP\n"
                                + "\n".join(
                                    f"{s['timestamp']},{s['student_id']},{s['student_name']},{s['section']},{s['u_filename']},{s['s_filename']},{s['ip']}"
                                    for s in app.storage.general.get("submissions", [])
                                ),
                                f"submissions{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            ),
                        ),
                    ).bind_enabled_from(app.storage.general, "submissions")
                    ui.button(
                        "Delete All",
                        on_click=show_delete_all_confirmation,
                    ).props("color=negative").bind_enabled_from(
                        app.storage.general, "submissions"
                    )

            with ui.row():
                ui.label("Submissions").classes("text-xl font-bold")
                ui.button(
                    icon="refresh", on_click=generate_submissions_table.refresh
                ).props("dense rounded")

            generate_submissions_table()

            ui.separator()

            

            @ui.refreshable
            def display_submission_details():
                selected_submissions = app.storage.client.get("selected_submissions", [])
                submission_info = (
                    selected_submissions[0] if selected_submissions else {}
                )

                with ui.grid(columns="auto 1fr"):
                    ui.label("Selected submission details").classes(
                        "text-lg font-bold col-span-full"
                    )

                    ui.label("Student ID")
                    ui.label(f"{submission_info.get('student_id', 'N/A')}")

                    ui.label("Name")
                    ui.label(f"{submission_info.get('student_name', 'N/A')}")

                    ui.label("Section")
                    ui.label(f"{submission_info.get('section', 'N/A')}")

                    ui.label("Submitted At")
                    ui.label(f"{submission_info.get('timestamp', 'N/A')}")

                    ui.label("Filename")
                    ui.label(f"{submission_info.get('u_filename', 'N/A')}").classes(
                        "truncate"
                    ).tooltip(submission_info.get("u_filename", "N/A"))

                    ui.label("Saved Filename")
                    ui.label(f"{submission_info.get('s_filename', 'N/A')}").classes(
                        "truncate"
                    ).tooltip(submission_info.get("s_filename", "N/A"))

                    ui.label("IP Address")
                    ui.label(f"{submission_info.get('ip', 'N/A')}")

                    ui.button(
                        "Delete Submission",
                        on_click=lambda: show_delete_confirmation(submission_info),
                    ).props("color=negative").bind_enabled_from(
                        app.storage.client, "selected_submissions"
                    )

            display_submission_details()


@ui.page("/")
async def main_page(client: Client):
    with ui.card().classes("w-full max-w-xl mx-auto"):
        ui.label("Screen recording submission form").classes("text-2xl font-bold")

        def get_past_submission():
            for submission in app.storage.general.get("submissions", []):
                if submission.get("ip") == client.ip:
                    return submission
            return {}

        # Check if the user has already submitted
        submission = get_past_submission()
        if submission:
            # show past submission info
            with ui.card().classes("bg-yellow-100 border-yellow-300 w-full"):
                ui.label("You have already uploaded your screen recording!").classes(
                    "text-red-500 font-bold"
                )
                with ui.grid(columns="auto 1fr").props("dense"):
                    ui.label("Student ID")
                    ui.label(f"{submission.get('student_id', 'N/A')}")

                    ui.label("Name")
                    ui.label(f"{submission.get('student_name', 'N/A')}")

                    ui.label("Section")
                    ui.label(f"{submission.get('section', 'N/A')}")

                    ui.label("Submitted At")
                    ui.label(f"{submission.get('timestamp', 'N/A')}")

                    ui.label("Filename")
                    ui.label(f"{submission.get('u_filename', 'N/A')}").classes(
                        "truncate"
                    ).tooltip(
                        app.storage.user.get("submission_info", {}).get(
                            "u_filename", "N/A"
                        )
                    )

            # disable form submission
            app.storage.user["enable_form_submission"] = False
        else:
            # enable form submission
            app.storage.user["enable_form_submission"] = True

        with ui.grid(columns="auto 1fr"):
            ui.label("Course Code")
            ui.label(f"{app.storage.general.get('course_code', 'N/A')}")

            section = app.storage.general.get("section")
            ui.label("Section")
            ui.label(f"{int(section) if isinstance(section, float) else section}")

            ui.label("Semester")
            ui.label(
                f"{app.storage.general.get('semester', 'Summer')} {app.storage.general.get('year', str(datetime.datetime.now().year))}"
            )

        ui.separator()

        ui.select(
            label="ID and name",
            options=app.storage.general.get("students", []),
            clearable=True,
        ).classes("w-full").bind_value(app.storage.client, "selected_student")
        ui.upload(
            label="Upload screen recording",
            on_upload=lambda file: app.storage.client.update({"file": file}),
            auto_upload=True,
            max_files=1,
        ).classes("w-full").props('accept="video/*"')

        def handle_submit():
            if not app.storage.general.get("enable_form_submission", True):
                ui.notify(
                    "Form submission is currently disabled. Please contact the admin.",
                    color="negative",
                )
                return

            selected_student = app.storage.client.get("selected_student")
            uploaded_file = app.storage.client.get("file")

            if not selected_student or not uploaded_file:
                ui.notify(
                    "Please select your name and upload a file.", color="negative"
                )
                return

            # Extract student ID from selected_student (format: "ID - Name")
            student_id = selected_student.split("-")[0].strip()
            section = app.storage.general.get("section", 1)

            # Ensure submissions directory exists
            submissions_dir = Path("submissions")
            submissions_dir.mkdir(exist_ok=True)

            # Save the uploaded file
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = (
                f"sec{int(section)}_{student_id}_{timestamp}_{uploaded_file.name}"
            )
            file_path = submissions_dir / filename

            with open(file_path, "wb") as f:
                f.write(uploaded_file.content.read())

            ui.notify("Submission successful!", color="positive")
            submission_info = {
                "student_id": student_id,
                "student_name": selected_student.split("-")[1].strip(),
                "section": section,
                "timestamp": datetime.datetime.now(),
                "s_filename": filename,
                "u_filename": uploaded_file.name,
                "ip": client.ip,
            }
            app.storage.general["submissions"].append(submission_info)
            app.storage.user["submission_info"] = submission_info

            ui.navigate.to("/submitted")

        ui.button("Submit", on_click=handle_submit).bind_enabled(
            app.storage.user, "enable_form_submission"
        ).classes("w-full")


@ui.page("/submitted")
def submitted_page():
    if app.storage.user.get("submission_info", {}):
        with ui.card().classes("w-full max-w-xl mx-auto"):
            ui.label("Your submission has been recorded!").classes("text-2xl font-bold")

            with ui.card().classes("bg-yellow-100 border-yellow-300 w-full"):
                with ui.grid(columns="auto 1fr").props("dense"):
                    ui.label("Student ID")
                    ui.label(
                        f"{app.storage.user.get('submission_info', {}).get('student_id', 'N/A')}"
                    )

                    ui.label("Name")
                    ui.label(
                        f"{app.storage.user.get('submission_info', {}).get('student_name', 'N/A')}"
                    )

                    ui.label("Section")
                    ui.label(
                        f"{app.storage.user.get('submission_info', {}).get('section', 'N/A')}"
                    )

                    ui.label("Submitted At")
                    ui.label(
                        f"{app.storage.user.get('submission_info', {}).get('timestamp', 'N/A')}"
                    )

                    ui.label("Filename")
                    ui.label(
                        f"{app.storage.user.get('submission_info', {}).get('u_filename', 'N/A')}"
                    ).classes("truncate").tooltip(
                        app.storage.user.get("submission_info", {}).get(
                            "u_filename", "N/A"
                        )
                    )

            app.storage.user.pop("submission_info")

    else:
        ui.navigate.to("/")


ui.run(storage_secret="secret is overrated")
