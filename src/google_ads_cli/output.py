from __future__ import annotations

import csv
import json
import sys
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from google.protobuf.json_format import MessageToDict
from rich.console import Console
from rich.table import Table

from google_ads_cli.errors import CliError

OUTPUT_FORMATS = ("table", "json", "jsonl", "csv")


def message_to_dict(message: Any) -> dict[str, Any]:
    protobuf = getattr(message, "_pb", message)
    return MessageToDict(
        protobuf,
        preserving_proto_field_name=True,
        use_integers_for_enums=False,
    )


def flatten(value: Mapping[str, Any], prefix: str = "") -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, item in value.items():
        field = f"{prefix}.{key}" if prefix else key
        if isinstance(item, Mapping):
            result.update(flatten(item, field))
        elif isinstance(item, list):
            result[field] = json.dumps(item, ensure_ascii=False, separators=(",", ":"))
        else:
            result[field] = item
    return result


def _as_records(data: Any) -> list[dict[str, Any]]:
    if data is None:
        return []
    if isinstance(data, Mapping):
        return [dict(data)]
    if isinstance(data, Sequence) and not isinstance(data, (str, bytes, bytearray)):
        records: list[dict[str, Any]] = []
        for item in data:
            if isinstance(item, Mapping):
                records.append(dict(item))
            else:
                records.append({"value": item})
        return records
    return [{"value": data}]


class Output:
    def __init__(self, output_format: str, *, no_color: bool = False) -> None:
        if output_format not in OUTPUT_FORMATS:
            raise CliError(f"Unsupported output format: {output_format}")
        self.output_format = output_format
        self.console = Console(no_color=no_color, highlight=False)

    def render(
        self,
        data: Any,
        *,
        title: str | None = None,
        columns: Iterable[str] | None = None,
    ) -> None:
        if self.output_format == "json":
            sys.stdout.write(json.dumps(data, ensure_ascii=False, indent=2, default=str) + "\n")
            return
        records = _as_records(data)
        if self.output_format == "jsonl":
            for record in records:
                sys.stdout.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
            return
        flat_records = [flatten(record) for record in records]
        selected_columns = list(columns or [])
        if not selected_columns:
            selected_columns = list(dict.fromkeys(key for row in flat_records for key in row))
        if self.output_format == "csv":
            writer = csv.DictWriter(sys.stdout, fieldnames=selected_columns, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(flat_records)
            return
        table = Table(title=title, show_lines=False)
        for column in selected_columns:
            table.add_column(column)
        for row in flat_records:
            table.add_row(*(str(row.get(column, "")) for column in selected_columns))
        self.console.print(table)

    def note(self, message: str) -> None:
        self.console.print(message)
