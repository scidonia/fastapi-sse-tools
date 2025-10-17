"""
Reusable FastAPI SSE (Server-Sent Events) utilities for OpenAPI schema generation.
"""

from typing import List, Dict, Any, Type, Optional, Callable, Union
from pydantic import BaseModel
from dataclasses import dataclass


@dataclass
class SSEEvent:
    """Represents an SSE event with all possible fields."""

    data: str
    event: Optional[str] = None
    id: Optional[str] = None
    retry: Optional[int] = None
    comment: Optional[str] = None

    def format(self) -> str:
        """Format as SSE event string."""
        lines = []
        if self.comment:
            lines.append(f": {self.comment}")
        if self.id is not None:
            lines.append(f"id: {self.id}")
        if self.event:
            lines.append(f"event: {self.event}")
        if self.retry is not None:
            lines.append(f"retry: {self.retry}")
        lines.append(f"data: {self.data}")
        lines.append("")  # Empty line to end event
        return "\n".join(lines)


def sse_schema_for(event_models: List[Type[BaseModel]]) -> Dict[str, Any]:
    """
    Generate an OpenAPI schema for an SSE endpoint with typed events.

    Args:
        event_models: List of Pydantic model classes that can be sent as SSE events

    Returns:
        OpenAPI schema dictionary for SSE content
    """
    one_of = [{"$ref": f"#/components/schemas/{m.__name__}"} for m in event_models]

    return {
        "content": {
            "text/event-stream": {
                "itemSchema": {"oneOf": one_of},  # OpenAPI 3.2+ compliant
                "schema": {  # Fallback for older tools
                    "oneOf": one_of,
                    "description": "Server-Sent Events stream",
                },
            }
        }
    }


def generate_sse_response_schema(
    event_models: List[Type[BaseModel]],
    description: str = "Server-Sent Events stream",
    event_descriptions: Optional[Dict[str, str]] = None,
    example_factories: Optional[Dict[Type[BaseModel], Callable[[], BaseModel]]] = None,
    event_names: Optional[Dict[Type[BaseModel], str]] = None,
    sse_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Generate a complete OpenAPI response schema for SSE endpoints.

    Args:
        event_models: List of Pydantic model classes that can be sent as SSE events
        description: Description of the SSE endpoint
        event_descriptions: Optional mapping of event names to descriptions
        example_factories: Optional mapping of model classes to factory functions that create examples
        event_names: Optional mapping of model classes to custom event names
        sse_config: Optional SSE configuration (retry intervals, etc.)

    Returns:
        Complete OpenAPI response schema dictionary
    """
    if event_descriptions is None:
        event_descriptions = {}

    if event_names is None:
        event_names = {model: model.__name__.lower() for model in event_models}

    if sse_config is None:
        sse_config = {}

    # Create examples using factories or defaults
    examples = {}
    for model in event_models:
        event_name = event_names[model]

        if example_factories and model in example_factories:
            # Use custom factory
            try:
                examples[event_name] = example_factories[model]()
            except Exception as e:
                # Factory failed, skip this example
                continue
        else:
            # Try default construction with better fallbacks
            try:
                # First try empty constructor
                examples[event_name] = model()
            except Exception:
                try:
                    # Try with minimal required fields
                    model_fields = model.model_fields
                    required_fields = {
                        name: _get_default_value_for_field(field_info)
                        for name, field_info in model_fields.items()
                        if field_info.is_required()
                    }
                    if required_fields:
                        examples[event_name] = model(**required_fields)
                    else:
                        # No required fields, but constructor failed - skip
                        continue
                except Exception:
                    # All attempts failed, skip this example
                    continue

    # Build event type descriptions
    event_type_descriptions = []
    for model in event_models:
        event_name = event_names[model]
        desc = event_descriptions.get(event_name, f"{model.__name__} events")
        event_type_descriptions.append(f"- `{event_name}`: {desc}")

    # Build example SSE stream with full SSE features
    example_lines = []
    event_id = 1

    for model in event_models:
        event_name = event_names[model]
        if event_name in examples:
            sse_event = SSEEvent(
                data=examples[event_name].model_dump_json(),
                event=event_name,
                id=str(event_id) if sse_config.get("include_ids", False) else None,
                retry=(
                    sse_config.get("retry_interval") if event_id == 1 else None
                ),  # Only on first event
                comment=sse_config.get("comment") if event_id == 1 else None,
            )
            example_lines.extend(sse_event.format().split("\n"))
            event_id += 1

    full_description = (
        f"{description}\n\n"
        "Event Types:\n" + "\n".join(event_type_descriptions) + "\n\n"
        "Each event data field contains JSON matching one of the response schemas.\n\n"
    )

    if sse_config.get("include_ids"):
        full_description += (
            "Events include sequential IDs for client-side tracking.\n\n"
        )

    if sse_config.get("retry_interval"):
        full_description += (
            f"Client retry interval: {sse_config['retry_interval']}ms\n\n"
        )

    full_description += "Example:\n\n" "```\n" + "\n".join(example_lines) + "```"

    return {
        200: {
            "description": full_description,
            **sse_schema_for(event_models),
        }
    }


def _get_default_value_for_field(field_info) -> Any:
    """Get a reasonable default value for a Pydantic field."""
    annotation = field_info.annotation

    # Handle common types
    if annotation == str:
        return "example"
    elif annotation == int:
        return 0
    elif annotation == float:
        return 0.0
    elif annotation == bool:
        return False
    elif annotation == list or (
        hasattr(annotation, "__origin__") and annotation.__origin__ == list
    ):
        return []
    elif annotation == dict or (
        hasattr(annotation, "__origin__") and annotation.__origin__ == dict
    ):
        return {}
    else:
        # For complex types, return a placeholder string
        return f"example_{annotation.__name__ if hasattr(annotation, '__name__') else 'value'}"


def create_sse_event_examples(
    models_with_data: Dict[str, BaseModel],
    sse_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Create OpenAPI examples for SSE events with full SSE field support.

    Args:
        models_with_data: Dictionary mapping event names to example model instances
        sse_config: Optional SSE configuration for additional fields

    Returns:
        OpenAPI examples dictionary
    """
    if sse_config is None:
        sse_config = {}

    examples = {}
    event_id = 1

    for event_name, model_instance in models_with_data.items():
        sse_event = SSEEvent(
            data=model_instance.model_dump_json(),
            event=event_name,
            id=str(event_id) if sse_config.get("include_ids", False) else None,
            retry=sse_config.get("retry_interval") if event_id == 1 else None,
            comment=sse_config.get("comment") if event_id == 1 else None,
        )

        examples[f"{event_name}_event"] = {
            "summary": f"{event_name.title()} Event",
            "description": f"Server-Sent Event with {event_name} data",
            "value": sse_event.format(),
        }
        event_id += 1

    return examples


def create_example_factory(
    model_class: Type[BaseModel], **field_values
) -> Callable[[], BaseModel]:
    """
    Create a factory function for generating model examples with specific field values.

    Args:
        model_class: The Pydantic model class
        **field_values: Field values to use in the example

    Returns:
        Factory function that creates model instances

    Example:
        progress_factory = create_example_factory(
            ProgressUpdate,
            phrases_processed=100,
            chunks_created=10,
            message="Processing in progress..."
        )
    """

    def factory() -> BaseModel:
        return model_class(**field_values)

    return factory
