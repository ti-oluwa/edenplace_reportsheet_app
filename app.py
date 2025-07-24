import typing
import logging
import uuid
from contextlib import contextmanager
import tempfile
from pathlib import Path

import pandas as pd
from pandas.io.formats.style import Styler
import streamlit as st
from streamlit.runtime.uploaded_file_manager import UploadedFile

from src.sheets import (
    BroadSheetSchema,
    SubjectSchema,
    SubjectsScores,
    AggregatesValues,
    StudentResult,
    BroadSheetsData,
    SubjectsSchemas,
    AggregatesSchemas,
    get_grade,
    extract_broadsheets_data,
)
from src.reports import render_report_generation_form


logger = logging.getLogger(__name__)
st.set_page_config(
    page_title="EdenPlace Report Sheets Dashboard",
    layout="wide",
)


@contextmanager
def get_temporary_path(uploaded_file: UploadedFile):
    """
    Context manager to write uploaded file to a temporary file.
    Returns the path to the temporary file.
    The path remains valid only within the context manager.

    :param uploaded_file (UploadedFile): The uploaded file to write to a temporary file.
    :return: Path to the temporary file.
    """
    temp_dir = tempfile.TemporaryDirectory(dir=Path.cwd(), suffix=uuid.uuid4().hex)
    temp_file_path = Path(temp_dir.name).resolve() / str(uploaded_file.name)
    try:
        with open(temp_file_path, "wb") as temp_file:
            temp_file.write(uploaded_file.getbuffer())
            yield temp_file_path
    finally:
        temp_dir.cleanup()
        logger.debug(f"Temporary file {temp_file_path} cleaned up.")


def extract_broadsheets_file_data(broadsheets_file: UploadedFile) -> BroadSheetsData:
    """
    Extracts broadsheets data from an uploaded file.

    :param broadsheets_file (UploadedFile): The uploaded file containing broadsheets data.
    :return: Extracted broadsheets data.
    """
    with get_temporary_path(broadsheets_file) as temp_path:
        broadsheets_data = extract_broadsheets_data(temp_path)
    return broadsheets_data


def add_overall_obtainable_score_to_subjects_scores_columns(
    columns, subject_schema: SubjectSchema
) -> typing.List[str]:
    formatted_columns: typing.List[str] = []
    for column in columns:
        try:
            overall = subject_schema[column]["overall"]
        except KeyError:
            overall = None

        if overall:
            formatted_columns.append(f"{column} ({overall})")
        else:
            formatted_columns.append(column)

    return formatted_columns


def add_overall_obtainable_value_to_aggregates_columns(
    columns, aggregates_schemas: AggregatesSchemas
) -> typing.List[str]:
    formatted_columns: typing.List[str] = []
    for column in columns:
        overall = aggregates_schemas[column].get("overall", None)
        if overall is not None:
            overall = round(overall, ndigits=2)

        if overall:
            formatted_columns.append(f"{column} ({overall})")
        else:
            formatted_columns.append(column)

    return formatted_columns


def format_columns(columns) -> typing.List[str]:
    """
    Formats column names by replacing underscores with spaces and converting them to title case.

    :param columns (list[str]): List of column names.

    :return: Formatted column names.
    """
    return [column.replace("_", " ").upper() for column in columns]


def subjects_scores_to_dataframe(
    subjects_scores: SubjectsScores, subjects_schemas: SubjectsSchemas
) -> Styler:
    """
    Converts subjects scores to a pandas dataframe.
    Applying relevant formatting to the column headings

    :param subjects_scores (SubjectsScores): The subjects scores to convert to a dataframe.
    :param subjects_schemas (SubjectsSchemas): The subjects schemas to use for formatting the column headings.
    :return: The subjects scores as a pandas dataframe.
    """
    subjects_scores_df = pd.DataFrame(subjects_scores)
    # The column headings in the dataframe are the subject names
    # Pick any one the subject names (column headings)
    any_subject = str(subjects_scores_df.columns[0])
    # Fetch the subject's schema from the subjects section of the broadsheet schema
    any_subject_schema = subjects_schemas[any_subject]

    # Format the column headings on the main axis of the dataframe
    subjects_scores_df.columns = format_columns(subjects_scores_df.columns)
    # Task the transpose of the dataframe so the other (subject scores) axis column headings can be formatted
    subjects_scores_df = subjects_scores_df.T
    # Format the subject scores headings to add the overall obtainable score for the score type
    subjects_scores_df.columns = (
        add_overall_obtainable_score_to_subjects_scores_columns(
            columns=subjects_scores_df.columns,
            subject_schema=any_subject_schema,
        )
    )
    subjects_scores_df.columns = format_columns(subjects_scores_df.columns)
    subjects_scores_df = subjects_scores_df.style.format(precision=2, na_rep="nil")
    return subjects_scores_df


def aggregates_values_to_dataframe(
    aggregates_values: AggregatesValues, aggregates_schemas: AggregatesSchemas
) -> Styler:
    """
    Converts aggregates values to a pandas dataframe.
    Applying relevant formatting to the column headings

    :param aggregates_values (AggregatesValues): The aggregates values to convert to a dataframe.
    :param aggregates_schemas (AggregatesSchemas): The aggregates schemas to use for formatting the column headings.
    :return: The aggregates values as a pandas dataframe.
    """
    aggregates_values_df = pd.DataFrame([aggregates_values])
    aggregates_values_df.columns = add_overall_obtainable_value_to_aggregates_columns(
        columns=aggregates_values_df.columns,
        aggregates_schemas=aggregates_schemas,
    )
    aggregates_values_df.columns = format_columns(aggregates_values_df.columns)
    aggregates_values_df = aggregates_values_df.style.format(precision=2, na_rep="nil")
    return aggregates_values_df


def render_student_result_summary(
    student_result: StudentResult, broadsheet_schema: BroadSheetSchema
) -> None:
    """
    Renders a summary of a student's result in the app.

    :param student_result (StudentResult): The student's result to render.
    :param broadsheet_schema (BroadSheetSchema): The schema of the broadsheet containing the student's result.
    """
    subjects_scores = student_result["subjects"]
    aggregates_values = student_result["aggregates"]
    student_name = student_result["student"]
    subjects_schemas = broadsheet_schema["subjects"]
    aggregates_schemas = broadsheet_schema["aggregates"]

    st.caption("Result Summary 📜")

    if subjects_scores:
        subjects_scores_df = subjects_scores_to_dataframe(
            subjects_scores, subjects_schemas
        )
        # Display the student's subjects scores on table
        st.write("**Subjects Scores**")
        st.table(subjects_scores_df)
    else:
        st.info("Subject score data unavailable.")

    if aggregates_values:
        aggregates_values_df = aggregates_values_to_dataframe(
            aggregates_values, aggregates_schemas
        )
        # Display aggregates values on table
        st.write("**Aggregates**")
        st.table(aggregates_values_df)
    else:
        st.info("Aggregates data unavailable.")

    overall_percentage_obtainable = aggregates_schemas["sum total %"].get(
        "overall", None
    )
    overall_percentage_obtained = aggregates_values.get("sum total %", None)

    col1, col2 = st.columns(2, gap="large")
    with col1:
        col1.write(
            f"**Overall Percentage Obtainable:** {round(overall_percentage_obtainable, ndigits=1) if overall_percentage_obtainable else 'Cannot evaluate'}%"
        )

        col1.write(
            f"**Overall Percentage Obtained:** {round(overall_percentage_obtained, ndigits=1) if overall_percentage_obtained else 'Cannot evaluate'}%"
        )

    with col2:
        overall_grade = (
            get_grade(overall_percentage_obtained)
            if overall_percentage_obtained
            else None
        )
        col2.write(f"**Overall Grade:** {overall_grade or 'Cannot evaluate'}")

    st.write("\n")

    teachers_comment = student_result["teachers_comment"]
    coordinators_comment = student_result["coordinators_comment"]
    st.write("**Teacher's comment**: ")
    st.caption(teachers_comment or "Not given")
    st.write("**Coordinator's comment**: ")
    st.caption(coordinators_comment or "Not given")

    st.session_state.report_generation_data_submitted = False
    st.button(
        "Generate Report Sheet",
        type="secondary",
        key=uuid.uuid4().hex,
        help=f"Generate report sheet for {student_name}",
        use_container_width=True,
        on_click=lambda: render_report_generation_form(
            student_result, broadsheet_schema
        ),
    )


def render_broadsheets_data(broadsheets_data: BroadSheetsData) -> None:
    """
    Renders broadsheets data on the app.

    :param broadsheets_data (BroadSheetsData): The broadsheets data to render.
    """
    # The term/sheet names which are the keys in the broadsheet data will be used as tab names
    tab_names = list(broadsheets_data.keys())
    tabs = st.tabs(tab_names)

    for tab, tab_name in zip(tabs, tab_names):
        with tab:
            # Since the tab name are the keys in the broadsheet data
            # Get th dat
            tab_data = broadsheets_data[tab_name]
            students_results = tab_data["students_results"]
            broadsheet_schema = tab_data["broadsheet_schema"]

            if not students_results:
                tab.info("No result data available")
                continue

            tab.caption(f"***{len(students_results)} students***")
            for student_result in students_results:
                expander_label = f"**{student_result['student']}**"
                with st.expander(label=expander_label, expanded=False, icon="👨🏾‍🎓"):
                    render_student_result_summary(student_result, broadsheet_schema)


def main() -> None:
    """
    Main entry point for the app.

    Renders the main dashboard of the app.
    """
    st.header("EdenPlace Term Report Sheets Dashboard")
    st.text("Visualize and generate student term report sheets")
    st.caption(
        "Click the handle below or drag and drop a file to upload broadsheets file"
    )

    broadsheets_file = st.file_uploader(
        label="Upload Broadsheets File",
        type=["xlsx"],
        help="Upload file containing broadsheets whose data will be rendered on this page.",
        accept_multiple_files=False,
    )
    if not broadsheets_file:
        return

    try:
        broadsheets_data = extract_broadsheets_file_data(broadsheets_file)
    except Exception as exc:
        logger.exception(exc)
        st.error(
            "Error processing the uploaded file. Ensure that the file uploaded is of the expected type and format"
        )
        return
    else:
        render_broadsheets_data(broadsheets_data)


if __name__ == "__main__":
    nav = st.navigation(
        pages=[
            st.Page(main, default=True, title="Dashboard"),
        ]
    )
    nav.run()
