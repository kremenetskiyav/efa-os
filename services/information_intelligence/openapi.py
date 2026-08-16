"""Canonicalization, structural extraction and compatibility-oriented diffing."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any


HTTP_METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}
STRUCTURAL_KEYS = {
    "$ref", "type", "format", "nullable", "enum", "required", "properties",
    "items", "additionalProperties", "allOf", "oneOf", "anyOf", "not",
    "default", "readOnly", "writeOnly", "content", "schema", "name", "in",
    "operationId", "security", "securitySchemes", "requestBody", "parameters",
    "responses", "style", "explode", "allowEmptyValue", "deprecated",
    "scheme", "bearerFormat", "openIdConnectUrl", "flows", "authorizationUrl",
    "tokenUrl", "refreshUrl", "scopes",
}


class OpenAPIContractError(ValueError):
    pass


@dataclass(frozen=True)
class CanonicalDocument:
    document: dict[str, Any]
    raw_sha256: str
    canonical_sha256: str
    canonical_bytes: bytes


@dataclass(frozen=True)
class ContractDiff:
    classification: str
    changed_paths: tuple[str, ...]
    reasons: tuple[str, ...]


def canonicalize_openapi(raw: bytes | str) -> CanonicalDocument:
    raw_bytes = raw.encode("utf-8") if isinstance(raw, str) else raw
    try:
        document = json.loads(raw_bytes)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise OpenAPIContractError("OpenAPI source is not valid UTF-8 JSON") from error
    if not isinstance(document, dict) or not isinstance(document.get("paths"), dict):
        raise OpenAPIContractError("OpenAPI document must contain an object paths member")
    canonical = json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return CanonicalDocument(
        document,
        hashlib.sha256(raw_bytes).hexdigest(),
        hashlib.sha256(canonical).hexdigest(),
        canonical,
    )


MAP_KEYS = {"properties", "content", "responses", "schemas", "securitySchemes", "flows", "scopes"}


def _schema_shape(value: Any, *, preserve_keys: bool = False) -> Any:
    if isinstance(value, list):
        return [_schema_shape(item, preserve_keys=preserve_keys) for item in value]
    if not isinstance(value, dict):
        return value
    keys = sorted(value) if preserve_keys else [key for key in sorted(value) if key in STRUCTURAL_KEYS]
    return {
        key: _schema_shape(value[key], preserve_keys=key in MAP_KEYS)
        for key in keys
    }


def structural_contract(document: dict[str, Any]) -> dict[str, Any]:
    paths: dict[str, Any] = {}
    for path, path_item in sorted(document.get("paths", {}).items()):
        if not isinstance(path_item, dict):
            continue
        operations: dict[str, Any] = {}
        inherited_parameters = _schema_shape(path_item.get("parameters", []))
        for method, operation in sorted(path_item.items()):
            if method.lower() not in HTTP_METHODS or not isinstance(operation, dict):
                continue
            operations[method.lower()] = {
                "operationId": operation.get("operationId"),
                "parameters": inherited_parameters + _schema_shape(operation.get("parameters", [])),
                "requestBody": _schema_shape(operation.get("requestBody")),
                "responses": _schema_shape(operation.get("responses", {}), preserve_keys=True),
                "security": _schema_shape(operation.get("security", document.get("security", [])), preserve_keys=True),
            }
        paths[path] = operations
    components = document.get("components", {}) if isinstance(document.get("components"), dict) else {}
    return {
        "spec_version": document.get("openapi") or document.get("swagger"),
        "api_version": (document.get("info") or {}).get("version") if isinstance(document.get("info"), dict) else None,
        "paths": paths,
        "components": {
            "schemas": _schema_shape(components.get("schemas", {}), preserve_keys=True),
            "securitySchemes": _schema_shape(components.get("securitySchemes", {}), preserve_keys=True),
        },
        "security": _schema_shape(document.get("security", []), preserve_keys=True),
    }


def _pointer(parts: tuple[str, ...]) -> str:
    return "/" + "/".join(part.replace("~", "~0").replace("/", "~1") for part in parts)


def _walk_changes(old: Any, new: Any, parts: tuple[str, ...] = ()) -> list[tuple[str, str, Any, Any]]:
    if isinstance(old, dict) and isinstance(new, dict):
        changes: list[tuple[str, str, Any, Any]] = []
        for key in sorted(old.keys() - new.keys()):
            changes.append((_pointer(parts + (str(key),)), "removed", old[key], None))
        for key in sorted(new.keys() - old.keys()):
            changes.append((_pointer(parts + (str(key),)), "added", None, new[key]))
        for key in sorted(old.keys() & new.keys()):
            changes.extend(_walk_changes(old[key], new[key], parts + (str(key),)))
        return changes
    if old != new:
        return [(_pointer(parts), "changed", old, new)]
    return []


def _array_change(path: str, old: Any, new: Any) -> tuple[str, str] | None:
    if path.endswith("/enum") and isinstance(old, list) and isinstance(new, list):
        removed = set(map(json.dumps, old)) - set(map(json.dumps, new))
        added = set(map(json.dumps, new)) - set(map(json.dumps, old))
        if removed:
            return "BREAKING", "enum value removed"
        if added:
            return "REVIEW", "enum value added; strict consumers may reject it"
    if path.endswith("/required") and isinstance(old, list) and isinstance(new, list):
        if set(new) - set(old):
            return "BREAKING", "required field added"
        if set(old) - set(new):
            return "NON_BREAKING", "required constraint relaxed"
    return None


def _classify_change(path: str, kind: str, old: Any, new: Any) -> tuple[str, str]:
    array_result = _array_change(path, old, new)
    if array_result:
        return array_result
    if "/security" in path or "/securitySchemes" in path:
        return "BREAKING", "security contract changed"
    if path.endswith("/type") and kind == "changed":
        return "BREAKING", "field type changed"
    if path.endswith("/format") or path.endswith("/nullable") or path.endswith("/default"):
        return "REVIEW", "format, nullable or default changed"
    tokens = path.split("/")
    if len(tokens) == 3 and tokens[1] == "paths":
        return ("BREAKING", "endpoint removed") if kind == "removed" else ("NON_BREAKING", "endpoint added")
    if len(tokens) == 4 and tokens[1] == "paths" and tokens[3] in HTTP_METHODS:
        return ("BREAKING", "endpoint or HTTP method removed") if kind == "removed" else ("NON_BREAKING", "endpoint added")
    if len(tokens) == 4 and tokens[1:3] == ["components", "schemas"]:
        return ("BREAKING", "schema removed") if kind == "removed" else ("NON_BREAKING", "schema added")
    if "/properties/" in path:
        if kind == "added":
            return "NON_BREAKING", "optional field added"
        if kind == "removed":
            return "REVIEW", "field removed; required use must be resolved"
    if "/responses/" in path and kind == "added":
        return "NON_BREAKING", "response added"
    if path.endswith("/operationId"):
        return "REVIEW", "operationId changed"
    return "REVIEW", "structural compatibility is not provable"


def _decode_pointer(path: str) -> list[str]:
    return [part.replace("~1", "/").replace("~0", "~") for part in path.lstrip("/").split("/") if part]


def _required_property_removed(path: str, kind: str, old_structure: dict[str, Any]) -> bool:
    if kind != "removed" or "/properties/" not in path:
        return False
    tokens = _decode_pointer(path)
    property_index = tokens.index("properties")
    parent_tokens = tokens[:property_index]
    property_name = tokens[property_index + 1]
    current: Any = old_structure
    for token in parent_tokens:
        if not isinstance(current, dict) or token not in current:
            return False
        current = current[token]
    return isinstance(current, dict) and property_name in current.get("required", [])


RANK = {"INFO_ONLY": 0, "NON_BREAKING": 1, "REVIEW": 2, "BREAKING": 3}


def diff_openapi(old_document: dict[str, Any], new_document: dict[str, Any]) -> ContractDiff:
    old_canonical = json.dumps(old_document, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    new_canonical = json.dumps(new_document, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if old_canonical == new_canonical:
        return ContractDiff("NO_CHANGE", (), ())
    old_structure = structural_contract(old_document)
    new_structure = structural_contract(new_document)
    if old_structure == new_structure:
        return ContractDiff("INFO_ONLY", (), ("non-structural metadata changed",))
    changes = _walk_changes(old_structure, new_structure)
    classified = [
        ("BREAKING", "required field removed")
        if _required_property_removed(change[0], change[1], old_structure)
        else _classify_change(*change)
        for change in changes
    ]
    classification = max((item[0] for item in classified), key=RANK.__getitem__)
    return ContractDiff(
        classification,
        tuple(change[0] for change in changes),
        tuple(dict.fromkeys(item[1] for item in classified)),
    )
