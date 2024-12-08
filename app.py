from contextlib import contextmanager
import typing
import uuid
import pandas as pd
import streamlit as st
from streamlit.runtime.uploaded_file_manager import UploadedFile

import tempfile
from pathlib import Path
import utils

st.set_page_config(
    page_title="EdenPlace Report Sheet Dashboard",
    page_icon="🏫",
    layout="wide",
)


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
        sheet_data = utils.extract_broadsheet_data(temp_file_path)
    return sheet_data


def format_columns(columns):
    """
    Formats column names by replacing underscores with spaces and converting them to title case.

    :param columns (list[str]): List of column names.

    :return: Formatted column names.
    """
    return [col.replace("_", " ").upper() for col in columns]


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
            sheet_data = handle_uploaded_broadsheet(uploaded_broadsheet)
        except Exception as exc:
            print(exc)
            st.error(
                "Error processing the uploaded file. Ensure that the file uploaded is of the expected type and format"
            )
            return

        tab_names = list(sheet_data.keys())
        tabs = st.tabs(tab_names)
        for index, tab in enumerate(tabs):
            with tab:
                tab_name = tab_names[index]
                students_results: typing.List[utils.StudentResult] = sheet_data[
                    tab_name
                ]
                if not students_results:
                    tab.info("No result data available")
                    continue

                for student_result in students_results:
                    student_name = f"**{student_result['student'].title()}**"

                    with st.expander(label=student_name, expanded=False, icon="🧑‍🎓"):
                        st.caption("Report Summary 📜")

                        # Display subjects
                        st.write("**Subjects**")
                        subjects = student_result["subjects"]
                        if subjects:
                            subjects_df = pd.DataFrame(subjects)
                            subjects_df.columns = format_columns(subjects_df.columns)
                            subjects_df = subjects_df.T
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
                        if aggregates:
                            aggregates_df = pd.DataFrame([aggregates])
                            aggregates_df.columns = format_columns(
                                aggregates_df.columns
                            )
                            aggregates_df = aggregates_df.style.format(
                                precision=2, na_rep="nil"
                            )
                            st.table(aggregates_df)
                        else:
                            st.info("No aggregates data available.")

                        st.button(
                            "Generate report sheet",
                            type="secondary",
                            key=uuid.uuid4().hex,
                            help=f"Generate report sheet for {student_name}",
                            use_container_width=True,
                        )


if __name__ == "__main__":
    main()
