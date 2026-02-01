"""Message Service Module.

Handles message sending, forwarding, and processing with Dify integration.

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Dict, Any, Optional, Tuple
import logging
import xml.etree.ElementTree as ET

from services.gewe.protocols import GeweServiceBase

logger = logging.getLogger(__name__)


class MessageServiceMixin(GeweServiceBase):
    """Mixin for message-related service methods"""

    async def send_text_message(
        self,
        app_id: str,
        to_wxid: str,
        content: str,
        ats: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send text message via WeChat."""
        client = self._get_gewe_client()
        return await client.post_text(
            app_id=app_id,
            to_wxid=to_wxid,
            content=content,
            ats=ats
        )

    async def send_file_message(
        self,
        app_id: str,
        to_wxid: str,
        file_url: str,
        file_name: str
    ) -> Dict[str, Any]:
        """Send file message."""
        client = self._get_gewe_client()
        return await client.post_file(
            app_id=app_id,
            to_wxid=to_wxid,
            file_url=file_url,
            file_name=file_name
        )

    async def send_image_message(
        self,
        app_id: str,
        to_wxid: str,
        img_url: str
    ) -> Dict[str, Any]:
        """Send image message."""
        client = self._get_gewe_client()
        return await client.post_image(
            app_id=app_id,
            to_wxid=to_wxid,
            img_url=img_url
        )

    async def send_voice_message(
        self,
        app_id: str,
        to_wxid: str,
        voice_url: str,
        voice_duration: int
    ) -> Dict[str, Any]:
        """Send voice message."""
        client = self._get_gewe_client()
        return await client.post_voice(
            app_id=app_id,
            to_wxid=to_wxid,
            voice_url=voice_url,
            voice_duration=voice_duration
        )

    async def send_video_message(
        self,
        app_id: str,
        to_wxid: str,
        video_url: str,
        thumb_url: str,
        video_duration: int
    ) -> Dict[str, Any]:
        """Send video message."""
        client = self._get_gewe_client()
        return await client.post_video(
            app_id=app_id,
            to_wxid=to_wxid,
            video_url=video_url,
            thumb_url=thumb_url,
            video_duration=video_duration
        )

    async def send_link_message(
        self,
        app_id: str,
        to_wxid: str,
        title: str,
        desc: str,
        link_url: str,
        thumb_url: str
    ) -> Dict[str, Any]:
        """Send link message."""
        client = self._get_gewe_client()
        return await client.post_link(
            app_id=app_id,
            to_wxid=to_wxid,
            title=title,
            desc=desc,
            link_url=link_url,
            thumb_url=thumb_url
        )

    async def send_name_card_message(
        self,
        app_id: str,
        to_wxid: str,
        nick_name: str,
        name_card_wxid: str
    ) -> Dict[str, Any]:
        """Send name card (contact card) message."""
        client = self._get_gewe_client()
        return await client.post_name_card(
            app_id=app_id,
            to_wxid=to_wxid,
            nick_name=nick_name,
            name_card_wxid=name_card_wxid
        )

    async def send_emoji_message(
        self,
        app_id: str,
        to_wxid: str,
        emoji_md5: str,
        emoji_size: int
    ) -> Dict[str, Any]:
        """Send emoji message."""
        client = self._get_gewe_client()
        return await client.post_emoji(
            app_id=app_id,
            to_wxid=to_wxid,
            emoji_md5=emoji_md5,
            emoji_size=emoji_size
        )

    async def send_app_message(
        self,
        app_id: str,
        to_wxid: str,
        appmsg: str
    ) -> Dict[str, Any]:
        """Send app message (mini-program, music share, etc.)."""
        client = self._get_gewe_client()
        return await client.post_app_msg(
            app_id=app_id,
            to_wxid=to_wxid,
            appmsg=appmsg
        )

    async def forward_file_message(
        self,
        app_id: str,
        to_wxid: str,
        xml: str
    ) -> Dict[str, Any]:
        """Forward file message using CDN info."""
        client = self._get_gewe_client()
        return await client.forward_file(
            app_id=app_id,
            to_wxid=to_wxid,
            xml=xml
        )

    async def forward_image_message(
        self,
        app_id: str,
        to_wxid: str,
        xml: str
    ) -> Dict[str, Any]:
        """Forward image message using CDN info."""
        client = self._get_gewe_client()
        return await client.forward_image(
            app_id=app_id,
            to_wxid=to_wxid,
            xml=xml
        )

    def _extract_text_from_message(
        self,
        message_data: Dict[str, Any]
    ) -> Optional[str]:
        """Extract text content from various message types for Dify processing."""
        type_name = message_data.get('TypeName', '')
        data = message_data.get('Data', {})
        msg_type = data.get('MsgType')

        if type_name == 'AddMsg':
            if msg_type == 1:
                return data.get('Content', {}).get('string', '').strip()
            elif msg_type == 3:
                push_content = data.get('PushContent', '')
                if push_content:
                    return f"[图片] {push_content}"
            elif msg_type == 34:
                push_content = data.get('PushContent', '')
                if push_content:
                    return f"[语音] {push_content}"
            elif msg_type == 43:
                push_content = data.get('PushContent', '')
                if push_content:
                    return f"[视频] {push_content}"
            elif msg_type == 47:
                push_content = data.get('PushContent', '')
                if push_content:
                    return f"[动画表情] {push_content}"
            elif msg_type == 48:
                push_content = data.get('PushContent', '')
                if push_content:
                    return f"[位置] {push_content}"
            elif msg_type == 42:
                push_content = data.get('PushContent', '')
                if push_content:
                    return f"[名片] {push_content}"
            elif msg_type == 37:
                content_xml = data.get('Content', {}).get('string', '')
                if content_xml:
                    try:
                        root = ET.fromstring(content_xml)
                        msg_elem = root.find('msg')
                        if msg_elem is not None:
                            content = msg_elem.get('content', '')
                            fromnickname = msg_elem.get('fromnickname', '')
                            if content:
                                return f"[好友添加请求] {fromnickname}: {content}"
                    except ET.ParseError:
                        pass
            elif msg_type == 49:
                content_xml = data.get('Content', {}).get('string', '')
                if content_xml:
                    try:
                        root = ET.fromstring(content_xml)
                        appmsg = root.find('.//appmsg')
                        if appmsg is not None:
                            appmsg_type = appmsg.find('type')
                            if appmsg_type is not None:
                                app_type = appmsg_type.text
                                title_elem = appmsg.find('title')
                                title = title_elem.text if title_elem is not None else ''
                                desc_elem = appmsg.find('des')
                                desc = desc_elem.text if desc_elem is not None else ''

                                if app_type == '5':
                                    return f"[链接] {title}: {desc}" if title else None
                                elif app_type == '6':
                                    return f"[文件] {title}" if title else None
                                elif app_type in ('33', '36'):
                                    return f"[小程序] {title}" if title else None
                                elif app_type == '57':
                                    return f"[引用消息] {title}" if title else None
                                elif app_type == '2000':
                                    return "[转账消息]"
                                elif app_type == '2001':
                                    return "[红包消息]"
                                elif app_type == '51':
                                    return "[视频号消息]"
                    except ET.ParseError:
                        pass
            elif msg_type == 10000:
                content = data.get('Content', {}).get('string', '')
                if content:
                    return f"[系统通知] {content}"
            elif msg_type == 10002:
                content_xml = data.get('Content', {}).get('string', '')
                if content_xml:
                    try:
                        root = ET.fromstring(content_xml)
                        sysmsg = root.find('sysmsg')
                        if sysmsg is not None:
                            sysmsg_type = sysmsg.get('type', '')
                            if sysmsg_type == 'revokemsg':
                                revokemsg = sysmsg.find('revokemsg')
                                if revokemsg is not None:
                                    replacemsg = revokemsg.find('replacemsg')
                                    if replacemsg is not None:
                                        return f"[撤回消息] {replacemsg.text}"
                            elif sysmsg_type == 'pat':
                                return "[拍一拍]"
                    except ET.ParseError:
                        pass

        elif type_name == 'ModContacts':
            nick_name = data.get('NickName', {}).get('string', '')
            if nick_name:
                return f"[联系人信息变更] {nick_name}"

        elif type_name == 'DelContacts':
            user_name = data.get('UserName', {}).get('string', '')
            if '@chatroom' in user_name:
                return f"[退出群聊] {user_name}"
            else:
                return f"[删除好友] {user_name}"

        elif type_name == 'Offline':
            logger.warning("Account offline: %s", message_data.get('Wxid', ''))
            return None

        return None

    def _is_group_chat_message(
        self,
        message_data: Dict[str, Any]
    ) -> bool:
        """Check if message is from a group chat."""
        data = message_data.get('Data', {})
        from_user = data.get('FromUserName', {}).get('string', '')
        to_user = data.get('ToUserName', {}).get('string', '')
        return '@chatroom' in from_user or '@chatroom' in to_user

    def _is_bot_mentioned(
        self,
        message_data: Dict[str, Any],
        text_content: str
    ) -> bool:
        """Check if bot is @mentioned in group chat message."""
        data = message_data.get('Data', {})
        msg_source = data.get('MsgSource', '')

        if '@' not in text_content:
            return False

        try:
            if msg_source:
                root = ET.fromstring(msg_source)
                alnode = root.find('alnode')
                if alnode is not None:
                    fr_elem = alnode.find('fr')
                    if fr_elem is not None:
                        fr_value = fr_elem.text
                        if fr_value == '1':
                            return True
        except ET.ParseError:
            pass

        if '@' in text_content:
            return True

        return False

    def _should_process_message(
        self,
        message_data: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """Determine if message should be processed and extract text content."""
        type_name = message_data.get('TypeName', '')
        data = message_data.get('Data', {})
        wxid = message_data.get('Wxid', '')

        from_user = data.get('FromUserName', {}).get('string', '')
        if from_user == wxid:
            logger.debug("Ignoring message from ourselves: %s", from_user)
            return False, None

        app_id = message_data.get('Appid', '')
        new_msg_id = data.get('NewMsgId')
        if new_msg_id:
            message_key = f"{app_id}_{new_msg_id}"
            if message_key in self._processed_messages:
                logger.debug("Ignoring duplicate message: %s", message_key)
                return False, None
            self._processed_messages.add(message_key)

        text_content = self._extract_text_from_message(message_data)

        if not text_content:
            logger.debug("No text content extracted from message type: %s, MsgType: %s",
                        type_name, data.get('MsgType'))
            return False, None

        is_group_chat = self._is_group_chat_message(message_data)

        if is_group_chat:
            if not self._is_bot_mentioned(message_data, text_content):
                logger.debug("Ignoring group chat message without @mention: %s", text_content[:50])
                return False, None
            logger.info("Processing @mentioned group chat message")

        return True, text_content

    async def process_incoming_message(
        self,
        message_data: Dict[str, Any]
    ) -> Tuple[Optional[str], Optional[str]]:
        """Process incoming WeChat message and generate Dify response."""
        try:
            wxid = message_data.get('Wxid', '')
            app_id = message_data.get('Appid', '')
            data = message_data.get('Data', {})
            from_user = data.get('FromUserName', {}).get('string', '')
            to_user = data.get('ToUserName', {}).get('string', '')
            msg_id = data.get('NewMsgId') or data.get('MsgId', 0)
            msg_type = data.get('MsgType', 0)

            # Save message to database (similar to xxxbot-pad)
            if app_id and msg_id:
                try:
                    content = data.get('Content', {}).get('string', '') or ''
                    is_group = self._is_group_chat_message(message_data)
                    sender_wxid = from_user
                    
                    # For group messages, extract actual sender
                    if is_group and content:
                        if ':\n' in content:
                            parts = content.split(':\n', 1)
                            if len(parts) > 1:
                                sender_wxid = parts[0]
                                content = parts[1]

                    self._message_db.save_message(
                        app_id=app_id,
                        msg_id=int(msg_id),
                        sender_wxid=sender_wxid,
                        from_wxid=from_user,
                        msg_type=int(msg_type),
                        content=content,
                        is_group=is_group
                    )
                except Exception as e:
                    logger.warning("Failed to save message to database: %s", e)

            should_process, text_content = self._should_process_message(message_data)
            if not should_process or not text_content:
                return None, None

            logger.info("Processing incoming message from %s: %s", from_user, text_content[:50])

            dify_client = self._get_dify_client()
            dify_user_id = f"gewe_{wxid}"

            is_group_chat = self._is_group_chat_message(message_data)
            if is_group_chat:
                response_to = to_user if '@chatroom' in to_user else from_user
                conversation_id = f"gewe_{wxid}_{response_to}"
            else:
                response_to = from_user
                conversation_id = f"gewe_{wxid}_{from_user}"

            response = await dify_client.chat_blocking(
                message=text_content,
                user_id=dify_user_id,
                conversation_id=conversation_id,
                auto_generate_name=False
            )

            answer = response.get('answer', '')
            if not answer:
                logger.warning("Dify returned empty answer")
                return None, None

            logger.info("Generated Dify response: %s", answer[:50])
            return answer, response_to

        except Exception as e:
            logger.error("Error processing incoming message: %s", e, exc_info=True)
            return None, None
