"""
FastAPI SSE Tools - Server-Sent Events utilities for OpenAPI schema generation.

This library provides utilities for creating properly documented Server-Sent Events
endpoints in FastAPI applications with full OpenAPI schema support.
"""

from .fastapi_sse import (
    SSEEvent,
    sse_schema_for,
    generate_sse_response_schema,
    create_sse_event_examples,
    create_example_factory,
)

__version__ = "0.1.0"

__all__ = [
    "SSEEvent",
    "sse_schema_for",
    "generate_sse_response_schema",
    "create_sse_event_examples",
    "create_example_factory",
]
