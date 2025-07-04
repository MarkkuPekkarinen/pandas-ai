import os.path
import shutil
import uuid

import pandas as pd
import pytest

import pandasai as pai
from pandasai.data_loader.semantic_layer_schema import (
    Transformation,
    TransformationParams,
)
from tests.integration_tests.conftest import (
    compare_sorted_dataframe,
    root_dir,
    set_fake_llm_output,
)

expected_df = pd.DataFrame(
    {
        "loan_status": ["paidoff", "collection", "collection_paidoff"],
        "average_age": [31.21, 30.61, 31.34],
    }
)


@pytest.fixture(scope="session")
def parquet_dataset_transformed_slug():
    df = pai.read_csv(f"{root_dir}/examples/data/loans_payments.csv")

    _id = uuid.uuid4()
    dataset_org = f"integration-test-organization-{_id}"
    dataset_path = f"testing-dataset-{_id}"
    dataset_slug = f"{dataset_org}/{dataset_path}"

    transformations = [
        Transformation(
            type="to_lowercase", params=TransformationParams(column="loan_status")
        ).model_dump()
    ]

    pai.create(
        dataset_slug,
        df,
        description="parquet with transformation",
        columns=[
            {"name": "loan_status"},
            {"name": "age", "expression": "avg(age)", "alias": "average_age"},
        ],
        group_by=["loan_status"],
        transformations=transformations,
    )

    yield dataset_slug
    shutil.rmtree(f"{root_dir}/datasets/{dataset_org}")


def test_parquet_files(parquet_dataset_transformed_slug, root_path):
    parquet_path = (
        f"{root_path}/datasets/{parquet_dataset_transformed_slug}/data.parquet"
    )
    schema_path = f"{root_path}/datasets/{parquet_dataset_transformed_slug}/schema.yaml"

    assert os.path.exists(parquet_path)
    assert os.path.exists(schema_path)


def test_parquet_load(parquet_dataset_transformed_slug):
    dataset = pai.load(parquet_dataset_transformed_slug)

    compare_sorted_dataframe(dataset, expected_df, "loan_status")


def test_parquet_chat(parquet_dataset_transformed_slug):
    dataset = pai.load(parquet_dataset_transformed_slug)

    set_fake_llm_output(
        output=f"""import pandas as pd
sql_query = 'SELECT * FROM {dataset.schema.name}'
df = execute_sql_query(sql_query)
result = {{'type': 'dataframe', 'value': df}}"""
    )

    result = dataset.chat("Give me all the dataset")
    compare_sorted_dataframe(result.value, expected_df, "loan_status")
