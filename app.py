from contextlib import contextmanager
import logging
import typing
import uuid
import pandas as pd
import streamlit as st
from streamlit.runtime.uploaded_file_manager import UploadedFile

import tempfile
from pathlib import Path
from utils import (
    BroadSheetSchema,
    SubjectSchema,
    SchemaInfo,
    extract_broadsheet_data,
    StudentResult,
    get_grade,
)

st.set_page_config(
    page_title="EdenPlace Report Sheet Dashboard",
    page_icon="🏫",
    layout="wide",
)

logger = logging.getLogger("edenplace-reportsheet")


@contextmanager
def temp_uploaded_file(uploaded_file: UploadedFile):
    with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
        # Define the file path within the temporary directory
        temp_file_path = Path(temp_dir).resolve() / str(uploaded_file.name)

        # Save the file to the temporary directory
        with open(temp_file_path, "wb") as temp_file:
            temp_file.write(uploaded_file.getbuffer())
        yield temp_file_path


def handle_uploaded_broadsheet(uploaded_broadsheet: UploadedFile):
    with temp_uploaded_file(uploaded_broadsheet) as temp_file_path:
        broadsheet_data = extract_broadsheet_data(temp_file_path)
    return broadsheet_data


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
    columns, aggregates_schema: typing.Dict[str, SchemaInfo]
):
    formatted_columns = []
    for column in columns:
        try:
            overall = aggregates_schema[column]["overall"]
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


def main():
    st.header("EdenPlace Report Sheet Dashboard")
    st.text("Visualize and generate student term report sheets")
    st.caption("Click the handle below or drag and drop a file to upload broadsheet")

    uploaded_broadsheet = st.file_uploader(
        label="Upload Broadsheet",
        type=["xlsx"],
        help="Upload broadsheet to visualize report data",
        accept_multiple_files=False,
    )

    if uploaded_broadsheet:
        try:
            broadsheet_data = handle_uploaded_broadsheet(uploaded_broadsheet)
        except Exception as exc:
            logger.error(exc)
            st.error(
                "Error processing the uploaded file. Ensure that the file uploaded is of the expected type and format"
            )
            return

        # The term/sheet names which are the keys in the broadsheet data will be used as tab names
        tab_names = list(broadsheet_data.keys())
        tabs = st.tabs(tab_names)
        for index, tab in enumerate(tabs):
            with tab:
                tab_name = tab_names[index]
                # Since the tab name are the keys in the broadsheet data
                # Get th dat
                tab_data = broadsheet_data[tab_name]
                students_results: typing.List[StudentResult] = tab_data[
                    "students_results"
                ]
                sheet_schema: BroadSheetSchema = tab_data[
                    "broadsheet_schema"
                ]
                
                if not students_results:
                    tab.info("No result data available")
                    continue

                tab.write(f"*{len(students_results)}* students")
                for student_result in students_results:
                    student_name = f"**{student_result['student'].title()}**"

                    with st.expander(label=student_name, expanded=False, icon="🧑‍🎓"):
                        st.caption("Report Summary 📜")

                        # Display subjects
                        st.write("**Subjects**")
                        subjects = student_result["subjects"]
                        if subjects:
                            subjects_df = pd.DataFrame(subjects)
                            # The column headings in the dataframe are the subject names
                            # Pick any one the subject names (column headings)
                            any_subject = subjects_df.columns[0]
                            # Fetch the subjects schema from the subjects section of the broadsheet schema
                            any_subject_schema = sheet_schema["subjects"][any_subject]

                            # Format the column headings on the main axis of the dataframe
                            subjects_df.columns = format_columns(subjects_df.columns)
                            # Task the transpose of the dataframe so the other (subject scores) axis column headings can be formatted
                            subjects_df = subjects_df.T
                            # Format the subject scores headings to add the overall obtainable score for the score type
                            subjects_df.columns = (
                                add_overall_obtainable_score_to_subjects_scores_columns(
                                    columns=subjects_df.columns,
                                    subject_schema=any_subject_schema,
                                )
                            )
                            subjects_df.columns = format_columns(subjects_df.columns)
                            subjects_df = subjects_df.style.format(
                                precision=2, na_rep="nil"
                            )
                            st.table(subjects_df)
                        else:
                            st.info("No subjects data available.")

                        # Display aggregates
                        st.write("**Aggregates**")
                        aggregates = student_result["aggregates"]
                        aggregates_schema = sheet_schema["aggregates"]
                        try:
                            overall_percentage_obtainable = aggregates_schema[
                                "sum total %"
                            ]["overall"]
                        except KeyError:
                            overall_percentage_obtainable = None
                        
                        overall_percentage_obtained = aggregates.get(
                            "sum total %", None
                        )

                        if aggregates:
                            aggregates_df = pd.DataFrame([aggregates])
                            aggregates_df.columns = (
                                add_overall_obtainable_value_to_aggregates_columns(
                                    columns=aggregates_df.columns,
                                    aggregates_schema=aggregates_schema,
                                )
                            )
                            aggregates_df.columns = format_columns(
                                aggregates_df.columns
                            )
                            aggregates_df = aggregates_df.style.format(
                                precision=2, na_rep="nil"
                            )
                            st.table(aggregates_df)
                        else:
                            st.info("No aggregates data available.")

                        col1, col2 = st.columns(2, gap="large")
                        with col1:
                            col1.write(
                                f"**Overall Percentage Obtainable: {round(overall_percentage_obtainable, ndigits=2) if overall_percentage_obtainable else "Cannot evaluate"}%**"
                            )

                            col1.write(
                                f"**Overall Percentage Obtained: {round(overall_percentage_obtained, ndigits=2) if overall_percentage_obtained else "Cannot evaluate"}%**"
                            )

                        with col2:
                            col2.write(
                                f"**Overall Grade: {get_grade(overall_percentage_obtained) or "Cannot evaluate"}**"
                            )

                        st.write("\n")

                        teachers_comment = student_result["teachers_comment"]
                        coordinators_comment = student_result["coordinators_comment"]
                        st.write("**Teacher's comment**: ")
                        st.caption(teachers_comment)
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

if __name__ == "__main__":
    main()
