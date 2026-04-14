"""DingTalk API base URLs and path constants (official OpenAPI + legacy oapi).

See:
https://open.dingtalk.com/document/orgapp-server/api-overview
https://open.dingtalk.com/document/development/bots-send-query-and-recall-group-chat-messages
"""

from __future__ import annotations

import os

DING_API_BASE = "https://api.dingtalk.com"
OAPI_MEDIA_UPLOAD = "https://oapi.dingtalk.com/media/upload"

PATH_OAUTH_ACCESS_TOKEN = "/v1.0/oauth2/accessToken"
PATH_ROBOT_MESSAGE_FILES_DOWNLOAD = "/v1.0/robot/messageFiles/download"
PATH_ROBOT_GROUP_MESSAGES_SEND = "/v1.0/robot/groupMessages/send"
PATH_ROBOT_OTO_MESSAGES_BATCH_SEND = "/v1.0/robot/oToMessages/batchSend"
PATH_ROBOT_GROUP_MESSAGES_BATCH_RECALL = "/v1.0/robot/groupMessages/batchRecall"
PATH_ROBOT_OTO_MESSAGES_BATCH_RECALL = "/v1.0/robot/otoMessages/batchRecall"
PATH_ROBOT_PRIVATE_CHAT_MESSAGES_QUERY = "/v1.0/robot/privateChatMessages/query"
PATH_ROBOT_GROUP_MESSAGES_QUERY = "/v1.0/robot/groupMessages/query"

PATH_CARD_INSTANCES_CREATE_AND_DELIVER = "/v1.0/card/instances/createAndDeliver"
# PUT /v1.0/card/streaming — official "AI card streaming update" (not PUT .../instances/{id}).
# Prereqs: enterprise app robot, Stream inbound mode, scope Card.Streaming.Write, template id.
# Group typing flow: (1) POST createAndDeliver with openSpaceId like
# dtv1.card//im_group.{openConversationId}, imGroupOpenSpaceModel + imGroupOpenDeliverModel,
# callbackType STREAM, cardData.cardParamMap; (2) PUT streaming with outTrackId + guid + key +
# full markdown per frame (isFull true for markdown vars). See open.dingtalk.com streaming API.
PATH_CARD_STREAMING_UPDATE = "/v1.0/card/streaming"

TOKEN_TTL_SECONDS = int(os.getenv("MINDBOT_DINGTALK_TOKEN_TTL", "6800"))
MAX_DOWNLOAD_MEDIA_BYTES = int(os.getenv("MINDBOT_MAX_MEDIA_BYTES", str(10 * 1024 * 1024)))

OAPI_MAX_IMAGE_BYTES = 1 * 1024 * 1024
OAPI_MAX_VOICE_BYTES = 2 * 1024 * 1024
OAPI_MAX_VIDEO_BYTES = 10 * 1024 * 1024
OAPI_MAX_FILE_BYTES = 10 * 1024 * 1024

ROBOT_RECALL_MAX_KEYS = 20
