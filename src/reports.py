import enum
from pathlib import Path
import typing
import jinja2
import jinja2.meta
import streamlit as st
from typing_extensions import TypedDict

from src.sheets import (
    StudentResult,
    BroadSheetSchema,
    SubjectSchema,
    SubjectsScores,
    AggregatesSchemas,
    AggregatesValues,
    get_grade,
)


def get_report_template(template_path: typing.Union[Path, str]) -> jinja2.Template:
    with open(template_path, "r") as template:
        report_template = jinja2.Template(source=template.read())
    return report_template


def get_template_variables(template_path: typing.Union[Path, str]) -> typing.List[str]:
    env = jinja2.Environment()
    with open(template_path, "r") as template:
        parsed_content = env.parse(template.read())
    return sorted(jinja2.meta.find_undeclared_variables(parsed_content))


PRIMARY_REPORT_TEMPLATE = get_report_template("./templates/primary_jinja.html")

PRIMARY_REPORT_TEMPLATE_VARIABLES = get_template_variables(
    "./templates/primary_jinja.html"
)


TEXT_TYPE_VARIABLES = {
    "class_name",
    "teachers_comment",
    "coordinators_comment",
    "term",
}
NUMBER_TYPE_VARIABLES = {
    "overall_percentage_obtained",
    "class_average_age",
    "number_of_students_in_class",
    "number_of_days_present",
    "number_of_days_absent",
    "number_of_days_school_opened",
}
DATE_TYPE_VARIABLES = {
    "term_end_date",
    "next_term_start_date",
}
EDITABLE_VARIABLES = {
    "term",
    "teachers_comment",
    "coordinators_comment",
}

BEHAVIOURAL_TRAITS = {
    "Punctuality",
    "Class Attendance",
    "Neatness",
    "Relationship with Others",
    "Sense of Responsibility",
    "Obedience",
    "Attentiveness",
    "Reliability",
    "Self-Control",
    "Spirit of Cooperation",
    "Honesty",
    "Handling of Tools",
    "Handwriting",
    "Games",
}


class ReportGenerationData(TypedDict):
    """Schema for the data required to generate a report sheet."""

    term: str
    student_name: str
    subjects_scores: SubjectsScores
    aggregates_values: AggregatesValues
    teachers_comment: typing.Optional[str]
    coordinators_comment: typing.Optional[str]
    overall_percentage_obtained: typing.Optional[float]
    overall_grade: typing.Optional[str]
    aggregates_schemas: AggregatesSchemas
    scores_schemas: SubjectSchema
    behavioural_scores: typing.Dict[str, str]


@st.cache_data
def get_default_report_generation_data(
    student_result: StudentResult, broadsheet_schema: BroadSheetSchema
) -> ReportGenerationData:
    subjects_schemas = broadsheet_schema["subjects"]
    first_subject = list(subjects_schemas.keys())[0]
    scores_schemas = subjects_schemas[first_subject]
    overall_percentage_obtained = student_result["aggregates"]["sum total %"]

    report_generation_data = ReportGenerationData(
        {
            "term": student_result["term"] or "",
            "student_name": student_result["student"],
            "subjects_scores": student_result["subjects"],
            "aggregates_values": student_result["aggregates"],
            "teachers_comment": student_result["teachers_comment"],
            "coordinators_comment": student_result["coordinators_comment"],
            "overall_percentage_obtained": round(overall_percentage_obtained, ndigits=1)
            if overall_percentage_obtained
            else None,
            "overall_grade": get_grade(overall_percentage_obtained).value
            if overall_percentage_obtained
            else None,
            "aggregates_schemas": broadsheet_schema["aggregates"],
            "scores_schemas": scores_schemas,
            "behavioural_scores": {
                trait: "E" for trait in BEHAVIOURAL_TRAITS
            },  # Default to 'E' for all traits
        }
    )
    return report_generation_data


class FormFieldType(str, enum.Enum):
    """Enumeration of form field types."""

    TEXT = "text"
    NUMBER = "number"
    DATE = "date"

    def __str__(self) -> str:
        return self.value


class FormFieldSchema(TypedDict):
    """Schema for kwargs used to create form fields."""

    label: str
    type: FormFieldType
    default: typing.Any


FormFieldsSchema = typing.Dict[str, FormFieldSchema]
"""Alias for the a collection of form field schemas."""


def get_report_generation_form_fields_schema(
    default_data: ReportGenerationData,
    variables: typing.Iterable[str],
    editable_variables: typing.Optional[typing.Iterable[str]] = None,
    exclude_variables: typing.Optional[typing.Iterable[str]] = None,
) -> FormFieldsSchema:
    """
    Generate a schema for the form fields required to build a
    report generation form.

    :param default_data: The default data to use for some/all the form fields.
    :param variables: The variables to generate form fields for.
    :param editable_variables: The variables that should be editable.
    :param exclude_variables: The variables to exclude from the form fields.
    :return: A schema for the form fields.
    """
    editable_variables = editable_variables or []
    schema: FormFieldsSchema = {}
    for variable in variables:
        value = default_data.get(variable, None)
        variable = variable.lower()

        if variable in default_data and variable not in editable_variables:
            continue
        if exclude_variables and variable in exclude_variables:
            continue

        schema[variable] = {
            "type": FormFieldType.TEXT,  # Default to text type
            "default": value,
            "label": variable.replace("_", " ").title(),
        }

        if variable in NUMBER_TYPE_VARIABLES:
            schema[variable]["type"] = FormFieldType.NUMBER
        elif variable in DATE_TYPE_VARIABLES:
            schema[variable]["type"] = FormFieldType.DATE
    return schema


@st.dialog("Generate Report Sheet", width="large")
def render_report_generation_form(
    student_result: StudentResult, broadsheet_schema: BroadSheetSchema
):
    """
    Render the form for requesting the required data to complete the report sheet generation.

    :param student_result: The student result data.
    :param broadsheet_schema: The schema of the broadsheet data from which the student result was extracted.
    :return: None
    """
    student_name = student_result["student"]
    report_generation_data = get_default_report_generation_data(
        student_result, broadsheet_schema
    )
    form_fields_schema = get_report_generation_form_fields_schema(
        default_data=report_generation_data,
        variables=PRIMARY_REPORT_TEMPLATE_VARIABLES,
        editable_variables=EDITABLE_VARIABLES,
        exclude_variables=["behavioural_scores"],
    )

    st.markdown(
        f"""
        **Fill the form below to generate {student_name}'s report sheet.**
        **Some of the data for the report sheet has been extracted from the broadsheet data.**
        **The data requested below is required to complete the report sheet.**
        """
    )

    for field, field_schema in form_fields_schema.items():
        label = field_schema["label"]

        if field_schema["type"] == "number":
            report_generation_data[field] = st.number_input(
                label, value=field_schema["default"], min_value=0, step=1
            )
        elif field_schema["type"] == "date":
            report_generation_data[field] = st.date_input(
                label, value=field_schema["default"]
            )
        else:
            report_generation_data[field] = st.text_input(
                label, value=field_schema["default"]
            )

    st.write(
        """
        **Behavioural Traits**

        - **A - Excellent level of observed trait**
        - **B - High level of observed trait**
        - **C - Acceptable level of observed trait**
        - **E - Unnoticed level of observed trait**

        """
    )
    for trait in BEHAVIOURAL_TRAITS:
        report_generation_data["behavioural_scores"][trait] = st.selectbox(
            trait,
            options=["A", "B", "C", "E"],
            help=f"Select grade for {trait!r}",
        )

    st.button(
        "Generate",
        help=f"Click to generate report sheet for {student_name!r}, then click download to save the report sheet.",
        use_container_width=True,
        type="secondary",
        on_click=lambda: setattr(
            st.session_state, "report_generation_data_submitted", True
        ),
    )

    missing_fields = set()
    for key, value in report_generation_data.items():
        if not value:
            missing_fields.add(key.replace("_", " ").title())

    submitted = st.session_state.get("report_generation_data_submitted", False)
    if submitted:
        if missing_fields:
            missing = "\n- ".join(missing_fields)
            st.error(
                f"""
                All fields are required to generate the report sheet.
                Please fill the following fields to generate the report sheet and try again;\n- {missing}
                """
            )
            return

        st.info("Click download to save the generated report sheet.")
        html_report_sheet = PRIMARY_REPORT_TEMPLATE.render(**report_generation_data)
        st.download_button(
            "Download Generated Sheet",
            data=html_report_sheet,
            file_name=f"{report_generation_data['student_name']} Report Sheet.html",
            mime="text/html",
            use_container_width=True,
        )
        st.session_state.report_generation_data_submitted = False
    return None
