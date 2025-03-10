from typing import Dict

from sqlglot import exp, expressions, parse_one, select
from sqlglot.expressions import Subquery
from sqlglot.optimizer.normalize_identifiers import normalize_identifiers

from ..data_loader.loader import DatasetLoader
from ..data_loader.semantic_layer_schema import SemanticLayerSchema
from ..helpers.sql_sanitizer import sanitize_view_column_name
from .base_query_builder import BaseQueryBuilder


class ViewQueryBuilder(BaseQueryBuilder):
    def __init__(
        self,
        schema: SemanticLayerSchema,
        schema_dependencies_dict: Dict[str, DatasetLoader],
    ):
        super().__init__(schema)
        self.schema_dependencies_dict = schema_dependencies_dict

    @staticmethod
    def normalize_view_column_name(name: str) -> str:
        return normalize_identifiers(parse_one(sanitize_view_column_name(name))).sql()

    @staticmethod
    def normalize_view_column_alias(name: str) -> str:
        return normalize_identifiers(
            sanitize_view_column_name(name).replace(".", "_")
        ).sql()

    def _get_columns(self) -> list[str]:
        if self.schema.columns:
            return [
                self.normalize_view_column_alias(col.name)
                for col in self.schema.columns
            ]
        else:
            return super()._get_columns()

    def _get_sub_query_from_loader(self, loader: DatasetLoader) -> Subquery:
        sub_query = parse_one(loader.query_builder.build_query())
        return exp.Subquery(this=sub_query, alias=loader.schema.name)

    def _get_table_expression(self) -> str:
        relations = self.schema.relations
        columns = self.schema.columns
        first_dataset = (
            relations[0].from_.split(".")[0]
            if relations
            else columns[0].name.split(".")[0]
        )
        first_loader = self.schema_dependencies_dict[first_dataset]
        first_query = self._get_sub_query_from_loader(first_loader)

        if self.schema.columns:
            columns = [
                f"{self.normalize_view_column_name(col.name)} AS {self.normalize_view_column_alias(col.name)}"
                for col in self.schema.columns
            ]
        else:
            columns = ["*"]

        query = select(*columns).from_(first_query)

        for relation in relations:
            to_datasets = relation.to.split(".")[0]
            loader = self.schema_dependencies_dict[to_datasets]
            subquery = self._get_sub_query_from_loader(loader)
            query = query.join(
                subquery,
                on=f"{sanitize_view_column_name(relation.from_)} = {sanitize_view_column_name(relation.to)}",
                append=True,
            )
        alias = normalize_identifiers(self.schema.name).sql()
        return exp.Subquery(this=query, alias=alias).sql(pretty=True)
