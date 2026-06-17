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

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
