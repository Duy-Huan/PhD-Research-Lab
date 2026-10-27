"""Bounded JSON Schema subset used to validate tool specifications, inputs and outputs (no new dependency).

Supported keywords: type (incl. lists), properties, required, additionalProperties (bool or schema), items, enum, const,
minimum/maximum, exclusiveMinimum/exclusiveMaximum, minLength/maxLength, pattern, minItems/maxItems, anyOf, description,
title, default and $defs/$ref to local "#/$defs/<name>" (pydantic output). Unknown keywords make a schema INVALID rather
than silently unchecked, so a tool can never ship a constraint the runtime would ignore.
"""
from __future__ import annotations

import re

KNOWN = {"type", "properties", "required", "additionalProperties", "items", "enum", "const", "minimum", "maximum",
         "exclusiveMinimum", "exclusiveMaximum", "minLength", "maxLength", "pattern", "minItems", "maxItems", "anyOf",
         "description", "title", "default", "$defs", "$ref", "examples", "format"}
TYPES = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None)}
MAX_DEPTH = 32


def _is(value, kind: str) -> bool:
    if kind == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, TYPES[kind])


def schema_errors(schema, path: str = "$", depth: int = 0) -> list[str]:
    """Structural problems in a schema itself (empty list = usable)."""
    if depth > MAX_DEPTH:
        return [f"{path}: schema nesting exceeds {MAX_DEPTH}"]
    if not isinstance(schema, dict):
        return [f"{path}: schema must be an object"]
    out = [f"{path}: unsupported keyword {k}" for k in schema if k not in KNOWN]
    kinds = schema.get("type", [])
    for kind in kinds if isinstance(kinds, list) else [kinds]:
        if kind not in TYPES and kind not in ("integer", "number"):
            out.append(f"{path}: unknown type {kind!r}")
    if "pattern" in schema:
        try:
            re.compile(schema["pattern"])
        except (re.error, TypeError):
            out.append(f"{path}: invalid pattern")
    for name, sub in (schema.get("properties") or {}).items():
        out += schema_errors(sub, f"{path}.{name}", depth + 1)
    for key in ("items",):
        if isinstance(schema.get(key), dict):
            out += schema_errors(schema[key], f"{path}[]", depth + 1)
    if isinstance(schema.get("additionalProperties"), dict):
        out += schema_errors(schema["additionalProperties"], f"{path}.*", depth + 1)
    for i, sub in enumerate(schema.get("anyOf") or []):
        out += schema_errors(sub, f"{path}|{i}", depth + 1)
    for name, sub in (schema.get("$defs") or {}).items():
        out += schema_errors(sub, f"{path}.$defs.{name}", depth + 1)
    if "$ref" in schema and not str(schema["$ref"]).startswith("#/$defs/"):
        out.append(f"{path}: only local #/$defs references are supported")
    if not isinstance(schema.get("required", []), list):
        out.append(f"{path}: required must be a list")
    return out


def validate(value, schema: dict, path: str = "$", root: dict | None = None, depth: int = 0) -> list[str]:
    """Validation errors for `value` (empty list = valid). Messages name the JSON path so an agent can correct its call."""
    root = root if root is not None else schema
    if depth > MAX_DEPTH:
        return [f"{path}: value nesting exceeds {MAX_DEPTH}"]
    if "$ref" in schema:
        target = (root.get("$defs") or {}).get(str(schema["$ref"]).rsplit("/", 1)[-1])
        if target is None:
            return [f"{path}: unresolved reference {schema['$ref']}"]
        return validate(value, target, path, root, depth + 1)
    if "anyOf" in schema:
        branches = [validate(value, s, path, root, depth + 1) for s in schema["anyOf"]]
        if all(branches):
            return [f"{path}: matches none of anyOf ({'; '.join(b[0] for b in branches)})"]
    kinds = schema.get("type")
    if kinds is not None:
        kinds = kinds if isinstance(kinds, list) else [kinds]
        if not any(_is(value, k) for k in kinds):
            return [f"{path}: expected {'/'.join(kinds)}, got {type(value).__name__}"]
    out = []
    if "const" in schema and value != schema["const"]:
        out.append(f"{path}: must equal {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        out.append(f"{path}: must be one of {schema['enum']!r}")
    if _is(value, "number"):
        for key, bad in (("minimum", lambda b: value < b), ("maximum", lambda b: value > b),
                         ("exclusiveMinimum", lambda b: value <= b), ("exclusiveMaximum", lambda b: value >= b)):
            if key in schema and bad(schema[key]):
                out.append(f"{path}: violates {key} {schema[key]}")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            out.append(f"{path}: shorter than {schema['minLength']}")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            out.append(f"{path}: longer than {schema['maxLength']}")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            out.append(f"{path}: does not match pattern {schema['pattern']}")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            out.append(f"{path}: fewer than {schema['minItems']} items")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            out.append(f"{path}: more than {schema['maxItems']} items")
        if isinstance(schema.get("items"), dict):
            for i, item in enumerate(value):
                out += validate(item, schema["items"], f"{path}[{i}]", root, depth + 1)
    if isinstance(value, dict):
        props = schema.get("properties") or {}
        out += [f"{path}.{k}: required" for k in schema.get("required", []) if k not in value]
        extra = schema.get("additionalProperties", True)
        for k, v in value.items():
            if k in props:
                out += validate(v, props[k], f"{path}.{k}", root, depth + 1)
            elif extra is False:
                out.append(f"{path}.{k}: unexpected property")
            elif isinstance(extra, dict):
                out += validate(v, extra, f"{path}.{k}", root, depth + 1)
    return out
