from __future__ import annotations

import base64
import copy
import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
from google.protobuf.json_format import MessageToDict, ParseDict

from google_ads_cli.ads_client import AdsSession, resolve_api_version, schema_client
from google_ads_cli.audit import append_audit, stable_hash
from google_ads_cli.errors import CliError, google_ads_error_details
from google_ads_cli.runtime import normalize_customer_id

VALID_ACTIONS = {"create", "update", "remove"}


@dataclass(slots=True)
class MutationOperation:
    resource: str
    action: str
    data: dict[str, Any] = field(default_factory=dict)
    resource_name: str | None = None
    update_mask: list[str] = field(default_factory=list)

    @classmethod
    def from_mapping(cls, raw: dict[str, Any], index: int) -> MutationOperation:
        allowed = {"resource", "action", "data", "resource_name", "update_mask"}
        unknown = sorted(set(raw) - allowed)
        if unknown:
            raise CliError(f"Operation {index}: unknown field(s): {', '.join(unknown)}")
        resource = raw.get("resource")
        action = raw.get("action")
        if not isinstance(resource, str) or not resource.strip():
            raise CliError(f"Operation {index}: `resource` must be a non-empty string")
        if action not in VALID_ACTIONS:
            raise CliError(
                f"Operation {index}: `action` must be one of {', '.join(sorted(VALID_ACTIONS))}"
            )
        data = raw.get("data") or {}
        if not isinstance(data, dict):
            raise CliError(f"Operation {index}: `data` must be a mapping")
        update_mask_raw = raw.get("update_mask") or []
        if isinstance(update_mask_raw, str):
            update_mask = [item.strip() for item in update_mask_raw.split(",") if item.strip()]
        elif isinstance(update_mask_raw, list) and all(
            isinstance(item, str) for item in update_mask_raw
        ):
            update_mask = update_mask_raw
        else:
            raise CliError(f"Operation {index}: `update_mask` must be a list or CSV string")
        resource_name = raw.get("resource_name")
        if resource_name is not None and not isinstance(resource_name, str):
            raise CliError(f"Operation {index}: `resource_name` must be a string")
        if action == "create" and not data:
            raise CliError(f"Operation {index}: create requires `data`")
        if action == "update" and not data and not resource_name:
            raise CliError(f"Operation {index}: update requires `data` or `resource_name`")
        if action == "update":
            update_resource_name = resource_name or _resource_name_from(data)
            if not update_resource_name:
                raise CliError(
                    f"Operation {index}: update requires `resource_name` in data or "
                    "at the operation level"
                )
            if not _resource_name_from(data):
                data = {"resourceName": update_resource_name, **data}
        if action == "remove" and not (resource_name or _resource_name_from(data)):
            raise CliError(f"Operation {index}: remove requires `resource_name`")
        return cls(
            resource=resource,
            action=action,
            data=data,
            resource_name=resource_name,
            update_mask=update_mask,
        )

    def to_mapping(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "resource": self.resource,
            "action": self.action,
        }
        if self.data:
            result["data"] = copy.deepcopy(self.data)
        if self.resource_name:
            result["resource_name"] = self.resource_name
        if self.update_mask:
            result["update_mask"] = list(self.update_mask)
        return result


@dataclass(slots=True)
class MutationPlan:
    customer_id: str
    operations: list[MutationOperation]
    api_version: str | None = None
    partial_failure: bool = False
    response_content_type: str = "RESOURCE_NAME_ONLY"
    label: str = "custom-mutation"

    @classmethod
    def from_mapping(cls, raw: dict[str, Any], customer_id: str | None = None) -> MutationPlan:
        allowed = {
            "customer_id",
            "api_version",
            "partial_failure",
            "response_content_type",
            "label",
            "operations",
        }
        unknown = sorted(set(raw) - allowed)
        if unknown:
            raise CliError(f"Unknown mutation plan field(s): {', '.join(unknown)}")
        selected_customer = customer_id or raw.get("customer_id")
        if not selected_customer:
            raise CliError("Mutation plan needs a customer_id (in the file or via --customer-id).")
        operations_raw = raw.get("operations")
        if not isinstance(operations_raw, list) or not operations_raw:
            raise CliError("Mutation plan `operations` must be a non-empty list.")
        operations = []
        for index, operation_raw in enumerate(operations_raw):
            if not isinstance(operation_raw, dict):
                raise CliError(f"Operation {index}: expected a mapping")
            operations.append(MutationOperation.from_mapping(operation_raw, index))
        response_type = str(raw.get("response_content_type", "RESOURCE_NAME_ONLY")).upper()
        if response_type not in {"RESOURCE_NAME_ONLY", "MUTABLE_RESOURCE"}:
            raise CliError("response_content_type must be RESOURCE_NAME_ONLY or MUTABLE_RESOURCE")
        partial_failure = raw.get("partial_failure", False)
        if not isinstance(partial_failure, bool):
            raise CliError("partial_failure must be true or false")
        api_version = raw.get("api_version")
        if api_version is not None and not isinstance(api_version, str):
            raise CliError("api_version must be a string such as v25")
        return cls(
            customer_id=normalize_customer_id(selected_customer),
            operations=operations,
            api_version=api_version,
            partial_failure=partial_failure,
            response_content_type=response_type,
            label=str(raw.get("label", "custom-mutation")),
        )

    def to_mapping(self, *, redact_large_values: bool = False) -> dict[str, Any]:
        data: dict[str, Any] = {
            "label": self.label,
            "customer_id": self.customer_id,
            "api_version": self.api_version,
            "partial_failure": self.partial_failure,
            "response_content_type": self.response_content_type,
            "operations": [operation.to_mapping() for operation in self.operations],
        }
        return _redact_large_values(data) if redact_large_values else data


def load_mutation_plan(path: Path, customer_id: str | None = None) -> MutationPlan:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise CliError(f"Could not read mutation plan {path}: {error}") from error
    if not isinstance(raw, dict):
        raise CliError("Mutation plan root must be a mapping.")
    return MutationPlan.from_mapping(raw, customer_id)


def _resource_name_from(data: dict[str, Any]) -> str | None:
    value = data.get("resource_name", data.get("resourceName"))
    return str(value) if value is not None else None


def _snake_case(value: str) -> str:
    value = value.replace("-", "_")
    return re.sub(r"(?<!^)(?=[A-Z])", "_", value).lower()


def _mask_paths(data: dict[str, Any], prefix: str = "") -> list[str]:
    paths: list[str] = []
    for raw_key, value in data.items():
        key = _snake_case(raw_key)
        if not prefix and key == "resource_name":
            continue
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict) and value:
            paths.extend(_mask_paths(value, path))
        else:
            paths.append(path)
    return paths


def _operation_field(resource: str) -> str:
    normalized = _snake_case(resource)
    if normalized.endswith("_operation"):
        return normalized
    return f"{normalized}_operation"


def compile_operations(
    client: GoogleAdsClient,
    operations: list[MutationOperation],
    *,
    api_version: str,
) -> list[Any]:
    probe = client.get_type("MutateOperation", version=api_version)
    valid_fields = {item.name for item in probe._pb.DESCRIPTOR.fields}
    compiled: list[Any] = []
    for index, item in enumerate(operations):
        field = _operation_field(item.resource)
        if field not in valid_fields:
            supported = ", ".join(sorted(name.removesuffix("_operation") for name in valid_fields))
            raise CliError(
                f"Operation {index}: resource `{item.resource}` is not supported by "
                f"GoogleAdsService.Mutate in {api_version}. Supported resources: {supported}"
            )
        operation = client.get_type("MutateOperation", version=api_version)
        nested = getattr(operation, field)
        try:
            if item.action == "remove":
                nested.remove = item.resource_name or _resource_name_from(item.data)
            else:
                target = getattr(nested, item.action)
                ParseDict(item.data, target._pb, ignore_unknown_fields=False)
                if item.action == "update":
                    paths = item.update_mask or _mask_paths(item.data)
                    if not paths:
                        raise CliError(f"Operation {index}: update mask is empty")
                    nested.update_mask.paths.extend(paths)
        except CliError:
            raise
        except Exception as error:
            raise CliError(
                f"Operation {index} ({item.resource}/{item.action}) does not match the "
                f"{api_version} protobuf schema: {error}"
            ) from error
        compiled.append(operation)
    return compiled


def validate_plan_schema(plan: MutationPlan, requested_version: str | None = None) -> str:
    version = resolve_api_version(requested_version or plan.api_version)
    compile_operations(schema_client(version), plan.operations, api_version=version)
    return version


def execute_plan(
    session: AdsSession,
    plan: MutationPlan,
    *,
    validate_only: bool,
) -> dict[str, Any]:
    version = resolve_api_version(plan.api_version or session.api_version)
    compiled = compile_operations(session.client, plan.operations, api_version=version)
    request = session.client.get_type("MutateGoogleAdsRequest", version=version)
    request.customer_id = plan.customer_id
    request.mutate_operations.extend(compiled)
    request.partial_failure = plan.partial_failure
    request.validate_only = validate_only
    request.response_content_type = plan.response_content_type
    mode = "validate_only" if validate_only else "execute"
    audit_base = {
        "action": plan.label,
        "mode": mode,
        "profile": session.profile_name,
        "customer_id": plan.customer_id,
        "api_version": version,
        "operation_count": len(plan.operations),
        "plan_sha256": stable_hash(plan.to_mapping()),
    }
    try:
        service = session.client.get_service("GoogleAdsService", version=version)
        response = service.mutate(request=request)
        result = MessageToDict(
            response._pb,
            preserving_proto_field_name=True,
            use_integers_for_enums=False,
        )
        partial_error = response.partial_failure_error
        has_partial_failure = bool(partial_error.code)
        if has_partial_failure:
            outcome = "partial_failure"
        else:
            outcome = "validated" if validate_only else "success"
        append_audit(
            {
                **audit_base,
                "outcome": outcome,
                "partial_failure_error": (
                    {
                        "code": partial_error.code,
                        "message": partial_error.message,
                    }
                    if has_partial_failure
                    else None
                ),
            }
        )
        return {
            "mode": mode,
            "customer_id": plan.customer_id,
            "api_version": version,
            "operation_count": len(plan.operations),
            "outcome": outcome,
            "response": result,
        }
    except GoogleAdsException as error:
        details = google_ads_error_details(error)
        append_audit(
            {
                **audit_base,
                "outcome": "error",
                "request_id": details.get("request_id"),
                "errors": details.get("errors"),
            }
        )
        raise


def plan_preview(plan: MutationPlan, version: str) -> dict[str, Any]:
    data = plan.to_mapping(redact_large_values=True)
    data["api_version"] = version
    data["mode"] = "plan"
    data["plan_sha256"] = stable_hash(plan.to_mapping())
    return data


def _redact_large_values(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _redact_large_values(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_large_values(item) for item in value]
    if isinstance(value, str) and len(value) > 512:
        try:
            raw = base64.b64decode(value, validate=True)
        except (ValueError, TypeError):
            raw = value.encode()
        digest = hashlib.sha256(raw).hexdigest()
        return f"<redacted-large-value bytes={len(raw)} sha256={digest}>"
    return value
