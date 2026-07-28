from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from google_ads_cli.ads_client import schema_client
from google_ads_cli.errors import CliError
from google_ads_cli.mutations import (
    MutationOperation,
    MutationPlan,
    compile_operations,
    load_mutation_plan,
    plan_preview,
)


def test_compile_generic_create_update_remove() -> None:
    operations = [
        MutationOperation(
            resource="campaign_budget",
            action="create",
            data={"name": "Budget", "amountMicros": "1000000", "explicitlyShared": False},
        ),
        MutationOperation(
            resource="campaign",
            action="update",
            data={
                "resourceName": "customers/1234567890/campaigns/1",
                "status": "PAUSED",
            },
        ),
        MutationOperation(
            resource="campaign",
            action="remove",
            resource_name="customers/1234567890/campaigns/2",
        ),
    ]
    compiled = compile_operations(schema_client("v25"), operations, api_version="v25")
    assert compiled[0].campaign_budget_operation.create.name == "Budget"
    assert list(compiled[1].campaign_operation.update_mask.paths) == ["status"]
    assert compiled[2].campaign_operation.remove.endswith("/2")


def test_bad_resource_and_bad_field_are_rejected() -> None:
    client = schema_client("v25")
    with pytest.raises(CliError, match="not supported"):
        compile_operations(
            client,
            [MutationOperation(resource="not_real", action="create", data={"name": "x"})],
            api_version="v25",
        )
    with pytest.raises(CliError, match="protobuf schema"):
        compile_operations(
            client,
            [MutationOperation(resource="campaign", action="create", data={"notAField": 1})],
            api_version="v25",
        )


def test_manifest_loader_and_large_value_redaction(tmp_path: Path) -> None:
    raw = {
        "customer_id": "123-456-7890",
        "operations": [
            {
                "resource": "asset",
                "action": "create",
                "data": {"imageAsset": {"data": "YQ==" * 200}},
            }
        ],
    }
    path = tmp_path / "plan.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    plan = load_mutation_plan(path)
    assert plan.customer_id == "1234567890"
    preview = plan_preview(plan, "v25")
    assert "redacted-large-value" in preview["operations"][0]["data"]["imageAsset"]["data"]


def test_manifest_requires_nonempty_operations() -> None:
    with pytest.raises(CliError, match="non-empty"):
        MutationPlan.from_mapping({"customer_id": "1234567890", "operations": []})


def test_manifest_rejects_string_boolean() -> None:
    with pytest.raises(CliError, match="true or false"):
        MutationPlan.from_mapping(
            {
                "customer_id": "1234567890",
                "partial_failure": "false",
                "operations": [
                    {
                        "resource": "campaign",
                        "action": "remove",
                        "resource_name": "customers/1234567890/campaigns/1",
                    }
                ],
            }
        )


def test_update_can_supply_resource_name_at_operation_level() -> None:
    plan = MutationPlan.from_mapping(
        {
            "customer_id": "1234567890",
            "operations": [
                {
                    "resource": "campaign",
                    "action": "update",
                    "resource_name": "customers/1234567890/campaigns/1",
                    "data": {"status": "PAUSED"},
                }
            ],
        }
    )
    assert plan.operations[0].data["resourceName"].endswith("/1")
