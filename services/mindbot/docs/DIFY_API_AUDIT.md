# Dify App API vs MindGraph `AsyncDifyClient` vs MindBot usage

Reference: [Dify Chat / App API](https://docs.dify.ai/guides/application-publishing/develop-with-apis) (align with your deployment’s version).

## Endpoint coverage (`clients/dify.py`)

| Dify API | `AsyncDifyClient` method | MindBot robot path |
|----------|--------------------------|--------------------|
| `POST /chat-messages` (streaming) | `stream_chat` | Yes |
| `POST /chat-messages` (blocking) | `chat_blocking` | Yes |
| `POST /chat-messages/{task_id}/stop` | `stop_chat` | No (not exposed to DingTalk flow) |
| `GET /messages` | `get_messages` | No |
| `POST /messages/{id}/feedbacks` | `message_feedback` | No |
| `GET /messages/{id}/suggested` | `get_suggested_questions` | No |
| Conversations list / delete / rename | `get_conversations`, `delete_conversation`, `rename_conversation` | No |
| Conversation variables | `get_conversation_variables`, `update_conversation_variable` | No |
| `POST /files/upload` | `upload_file` | Yes (user → Dify) |
| `GET /files/{id}/preview` | `get_file_preview_url`, `download_file` | Used indirectly for assistant files when needed |
| `POST /audio-to-text`, `POST /text-to-audio` | `audio_to_text`, `text_to_audio` | No (TTS in chat uses SSE `tts_*`, not this REST) |
| App info / parameters / meta / site | `get_app_info`, `get_app_parameters`, `get_app_meta`, `get_app_site` | No |
| Feedbacks / annotations | `get_app_feedbacks`, `get/create/update/delete_annotation`, etc. | No |

## Streaming events (MindBot consumer)

MindBot’s [`mindbot_consume_dify_stream_batched`](../core/dify_stream.py) maps Dify SSE to DingTalk. Text: `message`, `agent_message`. Native media: `message_file`, `tts_message` / `tts_message_end`. Workflow text fallback: `workflow_finished`. Moderation: `message_replace`. Usage: `message_end` metadata.

Intentionally unused in the robot pipeline: `stop_chat`, conversation CRUD, feedback, annotations—those are for other products or future admin features.

## Native assistant content (DingTalk)

Images, TTS audio, and non-image file links from Dify are sent via **DingTalk OpenAPI** (`sampleImageMsg`, `sampleAudio`, `sampleMarkdown` link lines). Session webhook remains **text/markdown only** for streaming chunks. Set `MINDBOT_OPENAPI_ENABLED` / `MINDBOT_FALLBACK_OPENAPI_SEND` appropriately; native media requires a successful OpenAPI path.

Env: `MINDBOT_DIFY_NATIVE_MEDIA_ENABLED`, `MINDBOT_DIFY_TTS_ENABLED`, `MINDBOT_STREAM_MAX_MEDIA_PARTS`, `MINDBOT_DIFY_WORKFLOW_FILE_KEYS` (optional comma-separated keys for workflow file outputs).
