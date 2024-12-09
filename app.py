import logging
import uuid
from contextlib import contextmanager
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit.runtime.uploaded_file_manager import UploadedFile

from sheet_utils import (
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


logger = logging.getLogger("edenplace-reportsheet")
st.set_page_config(
    page_title="EdenPlace Report Sheets Dashboard",
    layout="wide",
)


@contextmanager
def get_temporary_path(uploaded_file: UploadedFile):
    with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
        temp_file_path = Path(temp_dir).resolve() / str(uploaded_file.name)

        with open(temp_file_path, "wb") as temp_file:
            temp_file.write(uploaded_file.getbuffer())
        yield temp_file_path


def extract_broadsheets_file_data(broadsheets_file: UploadedFile):
    with get_temporary_path(broadsheets_file) as temp_path:
        broadsheets_data = extract_broadsheets_data(temp_path)
    return broadsheets_data


def add_overall_obtainable_score_to_subjects_scores_columns(
    columns, subject_schema: SubjectSchema
):
    formatted_columns = []
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
):
    formatted_columns = []
    for column in columns:
        try:
            overall = aggregates_schemas[column]["overall"]
        except KeyError:
            overall = None

        if overall:
            formatted_columns.append(f"{column} ({overall})")
        else:
            formatted_columns.append(column)

    return formatted_columns


def format_columns(columns):
    """
    Formats column names by replacing underscores with spaces and converting them to title case.

    :param columns (list[str]): List of column names.

    :return: Formatted column names.
    """
    return [column.replace("_", " ").upper() for column in columns]


def subjects_scores_to_dataframe(
    subjects_scores: SubjectsScores, subjects_schemas: SubjectsSchemas
):
    subjects_scores_df = pd.DataFrame(subjects_scores)
    # The column headings in the dataframe are the subject names
    # Pick any one the subject names (column headings)
    any_subject = subjects_scores_df.columns[0]
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
):
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
):
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

    try:
        overall_percentage_obtainable = aggregates_schemas["sum total %"]["overall"]
    except KeyError:
        overall_percentage_obtainable = None
    finally:
        overall_percentage_obtained = aggregates_values.get("sum total %", None)

    col1, col2 = st.columns(2, gap="large")
    with col1:
        col1.write(
            f"**Overall Percentage Obtainable:** {round(overall_percentage_obtainable, ndigits=2) if overall_percentage_obtainable else "Cannot evaluate"}%"
        )

        col1.write(
            f"**Overall Percentage Obtained:** {round(overall_percentage_obtained, ndigits=2) if overall_percentage_obtained else "Cannot evaluate"}%"
        )

    with col2:
        overall_grade = get_grade(overall_percentage_obtained)
        col2.write(f"**Overall Grade:** {overall_grade or "Cannot evaluate"}")

    st.write("\n")

    teachers_comment = student_result["teachers_comment"]
    coordinators_comment = student_result["coordinators_comment"]
    st.write("**Teacher's comment**: ")
    st.caption(teachers_comment or "Not given")
    st.write("**Coordinator's comment**: ")
    st.caption(coordinators_comment or "Not given")

    st.button(
        "Generate report sheet",
        type="secondary",
        key=uuid.uuid4().hex,
        help=f"Generate report sheet for {student_name}",
        use_container_width=True,
        disabled=True,
    )


def render_broadsheets_data(broadsheets_data: BroadSheetsData):
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
                expander_label = f"**```{student_result['student']}```**"
                with st.expander(label=expander_label, expanded=False, icon="👨🏾‍🎓"):
                    render_student_result_summary(student_result, broadsheet_schema)


def main():
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
        logger.error(exc)
        st.error(
            "Error processing the uploaded file. Ensure that the file uploaded is of the expected type and format"
        )
        return
    else:
        render_broadsheets_data(broadsheets_data)


if __name__ == "__main__":
    main()
