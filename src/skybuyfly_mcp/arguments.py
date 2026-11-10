# Copyright (c) 2026 PitchAI. Licensed under the MIT License (see LICENSE).
"""Tool arguments outside a tool's input schema, answered with the field and its format.

The SDK validates a call's arguments against the tool's input model and answers pydantic's own error text (type
codes, the rejected input and a link to pydantic's documentation site). This server middleware checks every
``tools/call`` first, against the same input model (``func_metadata`` of the tool's function, as the SDK builds it,
JSON-encoded values pre-parsed as the SDK does) and without raising (``SchemaValidator.isinstance_python``). A call
the model refuses is answered at once as a tool error naming the first wrong or missing field and its format (the
field's description, ``inputs``), counted in ``/mcp/metrics`` as ``InvalidArgumentsError`` and logged like every
other call (``runtime``). Any other call reaches the SDK unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from mcp.server.mcpserver.utilities.func_metadata import func_metadata
from mcp_types import CallToolResult, TextContent
from pydantic import BaseModel, JsonValue, create_model
from pydantic_core import SchemaValidator

from skybuyfly_mcp.metrics import client_family
from skybuyfly_mcp.runtime import DIRECT, REQUEST_CLIENT, AccessLine

if TYPE_CHECKING:
    from collections.abc import Mapping

    from mcp.server.context import CallNext, HandlerResult, ServerRequestContext
    from mcp.server.mcpserver.utilities.func_metadata import FuncMetadata
    from starlette.requests import Request

    from skybuyfly_mcp.metrics import Metrics
    from skybuyfly_mcp.tools import ToolFunction

INVALID: Final = "InvalidArgumentsError"
"""The outcome an argument check counts and logs."""
Arguments = dict[str, JsonValue]
"""A tool call's arguments, as the client sent them."""


class UndescribedInputError(TypeError):
    """A tool input without a type or a description: its argument errors could not name its format."""


class _CallParams(BaseModel):
    """The ``tools/call`` params the check reads."""

    name: str
    arguments: Arguments | None = None


_CALL_PARAMS = SchemaValidator(_CallParams.__pydantic_core_schema__)


@dataclass(frozen=True, slots=True)
class _Field:
    """One input field: the validator of a model holding it as ``value``, its description, and whether required."""

    validator: SchemaValidator
    description: str
    required: bool


@dataclass(frozen=True, slots=True)
class ToolArguments:
    """One tool's input model, as the SDK validates it, and each of its fields."""

    meta: FuncMetadata
    validator: SchemaValidator
    fields: Mapping[str, _Field]

    @classmethod
    def of(cls, function: ToolFunction) -> ToolArguments:
        """Build the checks of a tool function's input model.

        Returns:
            The tool's argument checks.

        Raises:
            UndescribedInputError: An input has no type or no description (a tool definition error, at startup).
        """
        meta = func_metadata(function)
        fields: dict[str, _Field] = {}
        for name, info in meta.arg_model.model_fields.items():
            if info.annotation is None or info.description is None:
                message = f"input {name!r} of {meta.arg_model.__name__} needs a type and a description (inputs)"
                raise UndescribedInputError(message)
            single = create_model(f"{meta.arg_model.__name__}_{name}", value=(info.annotation, info))
            validator = SchemaValidator(single.__pydantic_core_schema__)
            fields[name] = _Field(validator, info.description, info.is_required())
        return cls(meta, SchemaValidator(meta.arg_model.__pydantic_core_schema__), fields)

    def problem(self, tool: str, arguments: Arguments) -> str | None:
        """Return what is wrong with a call's arguments.

        Returns:
            The first wrong or missing field and its format, or ``None`` when the arguments are valid.
        """
        parsed = self.meta.pre_parse_json(arguments)
        if self.validator.isinstance_python(parsed):
            return None
        for name, field in self.fields.items():
            if name not in parsed:
                if field.required:
                    return f"Missing argument {name!r} of {tool}: {field.description}"
                continue
            if not field.validator.isinstance_python({"value": parsed[name]}):
                return f"Invalid argument {name!r} of {tool}. Expected: {field.description}"
        return f"Invalid arguments of {tool}: only the fields of its input schema are accepted."


@dataclass(frozen=True, slots=True)
class ArgumentCheck:
    """Server middleware: the module docstring's check, for every tool by name."""

    tools: Mapping[str, ToolArguments]
    metrics: Metrics

    async def __call__(
        self,
        ctx: ServerRequestContext[Arguments, Request],
        call_next: CallNext,
    ) -> HandlerResult:
        """Answer a ``tools/call`` with arguments its tool refuses; pass every other message on.

        Returns:
            The tool error, or the rest of the chain's result.
        """
        if ctx.method != "tools/call" or not _CALL_PARAMS.isinstance_python(ctx.params):
            return await call_next(ctx)
        params = _CallParams.model_validate(ctx.params)
        tool = self.tools.get(params.name)
        problem = None if tool is None else tool.problem(params.name, params.arguments or {})
        if problem is None:
            return await call_next(ctx)
        client = REQUEST_CLIENT.get() or DIRECT
        family = client_family(client.user_agent)
        self.metrics.record(params.name, INVALID, family, [])
        AccessLine(params.name, INVALID, 0, [], family).write()
        return CallToolResult(content=[TextContent(type="text", text=problem)], is_error=True)
