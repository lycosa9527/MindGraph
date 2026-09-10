"""Typed-text OpenAI-compatible tool loop for Kitty.

Import ``run_typed_agent_loop`` from ``services.kitty.agent_loop.loop``.
This package init stays import-light so routing helpers can use
``intent_clarify`` without a tools ↔ pending-clarify cycle.
"""
