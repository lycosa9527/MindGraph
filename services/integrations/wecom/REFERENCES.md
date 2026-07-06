# WeCom integration — official API references

| Topic | Doc path | Used by |
|-------|----------|---------|
| 消息推送 (webhook send + upload) | [99110](https://developer.work.weixin.qq.com/document/path/99110) | `webhook_client`, `webhook_payloads`, `webhook_media` |
| Legacy 消息推送 (same content) | [91770](https://developer.work.weixin.qq.com/document/path/91770) | alias of 99110 |
| gettoken | [91039](https://developer.work.weixin.qq.com/document/path/91039) | `app_message_client` |
| 发送应用消息 | [90236](https://developer.work.weixin.qq.com/document/path/90236) | `app_message_client` |

## Webhook msgtypes implemented (99110)

- `text` — `mentioned_list`, `mentioned_mobile_list`
- `markdown` — `content`; @ via `<@userid>` in content
- `markdown_v2` — richer formatting; no @ or font colors
- `news` — 1–8 articles
- `image` — base64 + md5
- `file` / `voice` — `media_id` from `upload_media`
- `template_card` — `text_notice` simplified builder

## Limits (99110)

- Webhook rate: 20 messages/minute per webhook
- Text: 2048 bytes UTF-8
- Markdown / markdown_v2: 4096 bytes UTF-8
- Image: ≤2 MB (JPG/PNG)
- File: ≤20 MB
- Voice: ≤2 MB, AMR, ≤60s playback
