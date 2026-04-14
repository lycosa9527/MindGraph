"""MindBot: multi-platform chat ↔ Dify (per-organization config).

Layout:

- ``core`` — Redis keys, Dify stream/blocking helpers
- ``dify`` — usage parsing, API health
- ``integrations.dingtalk`` — HTTP event subscription, inbound logging
- ``outbound`` — DingTalk session webhook + OpenAPI sends
- ``pipeline`` — callback orchestration, Dify reply paths
- ``platforms.<vendor>`` — low-level vendor APIs (e.g. ``platforms.dingtalk``)
- ``session`` — webhook URL validation, callback tokens
- ``telemetry`` — metrics, usage events, pipeline logging
- ``education`` — education/research metrics
"""
