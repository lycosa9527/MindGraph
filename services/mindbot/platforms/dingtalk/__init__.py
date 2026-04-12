"""DingTalk MindBot building blocks: OAuth, inbound parsing, session webhook, robot OpenAPI."""

from services.mindbot.platforms.dingtalk.inbound import (
    extract_dingtalk_sender_profile,
    extract_download_code_for_openapi,
    extract_inbound_prompt,
    media_filename_and_types,
)
from services.mindbot.platforms.dingtalk.media_upload import oapi_max_bytes_for_type, upload_media_oapi
from services.mindbot.platforms.dingtalk.message_files import (
    download_url_bytes,
    fetch_message_media_bytes,
    get_message_file_download_url,
)
from services.mindbot.platforms.dingtalk.oauth import get_access_token
from services.mindbot.platforms.dingtalk.robot_query import (
    query_group_robot_messages,
    query_private_chat_robot_messages,
)
from services.mindbot.platforms.dingtalk.robot_recall import (
    batch_recall_group_robot_messages,
    batch_recall_oto_robot_messages,
)
from services.mindbot.platforms.dingtalk.robot_send import (
    send_group_action_card_sample,
    send_group_audio_from_upload,
    send_group_file_from_upload,
    send_group_image_by_photo_url,
    send_group_link_sample,
    send_group_markdown_sample,
    send_group_robot_message,
    send_group_text_sample,
    send_group_video_from_upload,
    send_oto_robot_message,
    send_private_action_card_sample,
    send_private_audio_from_upload,
    send_private_file_from_upload,
    send_private_image_by_photo_url,
    send_private_link_sample,
    send_private_markdown_sample,
    send_private_text_sample,
    send_private_video_from_upload,
)
from services.mindbot.platforms.dingtalk.robot_templates import (
    msg_param_sample_action_card,
    msg_param_sample_audio,
    msg_param_sample_file,
    msg_param_sample_image,
    msg_param_sample_link,
    msg_param_sample_markdown,
    msg_param_sample_text,
    msg_param_sample_video,
)
from services.mindbot.platforms.dingtalk.session_webhook import (
    build_session_webhook_payload,
    markdown_title_and_body_for_openapi,
    openapi_robot_msg_param_for_answer,
    openapi_robot_msg_param_stream_chunk,
    sanitize_markdown_for_dingtalk,
)
from services.mindbot.platforms.dingtalk.verify import (
    compute_sign,
    extract_dingtalk_robot_auth_headers,
    verify_dingtalk_sign,
)

__all__ = [
    "batch_recall_group_robot_messages",
    "batch_recall_oto_robot_messages",
    "build_session_webhook_payload",
    "compute_sign",
    "extract_dingtalk_robot_auth_headers",
    "download_url_bytes",
    "extract_dingtalk_sender_profile",
    "extract_download_code_for_openapi",
    "extract_inbound_prompt",
    "fetch_message_media_bytes",
    "get_access_token",
    "get_message_file_download_url",
    "markdown_title_and_body_for_openapi",
    "media_filename_and_types",
    "msg_param_sample_action_card",
    "msg_param_sample_audio",
    "msg_param_sample_file",
    "msg_param_sample_image",
    "msg_param_sample_link",
    "msg_param_sample_markdown",
    "msg_param_sample_text",
    "msg_param_sample_video",
    "oapi_max_bytes_for_type",
    "openapi_robot_msg_param_for_answer",
    "openapi_robot_msg_param_stream_chunk",
    "query_group_robot_messages",
    "query_private_chat_robot_messages",
    "sanitize_markdown_for_dingtalk",
    "send_group_action_card_sample",
    "send_group_audio_from_upload",
    "send_group_file_from_upload",
    "send_group_image_by_photo_url",
    "send_group_link_sample",
    "send_group_markdown_sample",
    "send_group_robot_message",
    "send_group_text_sample",
    "send_group_video_from_upload",
    "send_oto_robot_message",
    "send_private_action_card_sample",
    "send_private_audio_from_upload",
    "send_private_file_from_upload",
    "send_private_image_by_photo_url",
    "send_private_link_sample",
    "send_private_markdown_sample",
    "send_private_text_sample",
    "send_private_video_from_upload",
    "upload_media_oapi",
    "verify_dingtalk_sign",
]
