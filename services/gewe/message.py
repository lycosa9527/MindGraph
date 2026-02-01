"""Message Service Module.

Handles message sending, forwarding, and processing with Dify integration.

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Dict, Any, Optional, Tuple, List
import logging
import re
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

    async def forward_video_message(
        self,
        app_id: str,
        to_wxid: str,
        xml: str
    ) -> Dict[str, Any]:
        """Forward video message using CDN info."""
        client = self._get_gewe_client()
        return await client.forward_video(
            app_id=app_id,
            to_wxid=to_wxid,
            xml=xml
        )

    async def forward_link_message(
        self,
        app_id: str,
        to_wxid: str,
        xml: str
    ) -> Dict[str, Any]:
        """Forward link message using CDN info."""
        client = self._get_gewe_client()
        return await client.forward_link(
            app_id=app_id,
            to_wxid=to_wxid,
            xml=xml
        )

    async def forward_mini_program_message(
        self,
        app_id: str,
        to_wxid: str,
        xml: str,
        cover_img_url: str
    ) -> Dict[str, Any]:
        """Forward mini-program message using CDN info."""
        client = self._get_gewe_client()
        return await client.forward_mini_program(
            app_id=app_id,
            to_wxid=to_wxid,
            xml=xml,
            cover_img_url=cover_img_url
        )

    async def revoke_message(
        self,
        app_id: str,
        to_wxid: str,
        msg_id: str,
        new_msg_id: str,
        create_time: str
    ) -> Dict[str, Any]:
        """
        Revoke (recall) a sent message.
        
        Requires msgId, newMsgId, and createTime from the original send response.
        """
        client = self._get_gewe_client()
        return await client.revoke_message(
            app_id=app_id,
            to_wxid=to_wxid,
            msg_id=msg_id,
            new_msg_id=new_msg_id,
            create_time=create_time
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
                                    quoted_msg = self._extract_quoted_message(message_data)
                                    if quoted_msg:
                                        quoted_content = quoted_msg.get('content', '')
                                        if quoted_content:
                                            if title:
                                                return f"{title} [回复: {quoted_content}]"
                                            return f"[回复: {quoted_content}]"
                                    return title if title else "[引用消息]"
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

    def _extract_quoted_message(
        self,
        message_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Extract quoted/replied-to message from message data."""
        data = message_data.get('Data', {})
        msg_type = data.get('MsgType', 0)

        if msg_type != 49:
            return None

        content_xml = data.get('Content', {}).get('string', '')
        if not content_xml:
            return None

        try:
            root = ET.fromstring(content_xml)
            appmsg = root.find('.//appmsg')
            if appmsg is None:
                return None

            appmsg_type = appmsg.find('type')
            if appmsg_type is None or appmsg_type.text != '57':
                return None

            refermsg = appmsg.find('refermsg')
            if refermsg is None:
                return None

            type_elem = refermsg.find('type')
            svrid_elem = refermsg.find('svrid')
            fromusr_elem = refermsg.find('fromusr')
            chatusr_elem = refermsg.find('chatusr')
            displayname_elem = refermsg.find('displayname')
            content_elem = refermsg.find('content')
            createtime_elem = refermsg.find('createtime')

            quoted_msg = {
                'msg_type': int(type_elem.text) if type_elem is not None and type_elem.text is not None else 0,
                'msg_id': svrid_elem.text if svrid_elem is not None and svrid_elem.text is not None else '',
                'from_wxid': fromusr_elem.text if fromusr_elem is not None and fromusr_elem.text is not None else '',
                'chat_wxid': chatusr_elem.text if chatusr_elem is not None and chatusr_elem.text is not None else '',
                'nickname': displayname_elem.text if displayname_elem is not None and displayname_elem.text is not None else '',
                'content': content_elem.text if content_elem is not None and content_elem.text is not None else '',
                'create_time': createtime_elem.text if createtime_elem is not None and createtime_elem.text is not None else '',
            }

            return quoted_msg

        except ET.ParseError as e:
            logger.warning("Failed to parse quoted message XML: %s", e)
            return None

    def _parse_markdown_images(
        self,
        text: str
    ) -> Tuple[str, List[str]]:
        """
        Parse markdown image syntax from text.

        Returns:
            Tuple of (text_without_images, list_of_image_urls)
        """
        pattern = r'!\[([^\]]*)\]\(([^\)]+)(?:\s+"[^"]*")?\)'

        image_urls = []
        text_without_images = text

        for match in re.finditer(pattern, text):
            image_url = match.group(2).strip()
            if image_url.startswith('http://') or image_url.startswith('https://'):
                image_urls.append(image_url)
                text_without_images = text_without_images.replace(match.group(0), '')

        text_without_images = re.sub(r'\n\s*\n\s*\n', '\n\n', text_without_images).strip()

        return text_without_images, image_urls

    def _is_group_chat_message(
        self,
        message_data: Dict[str, Any]
    ) -> bool:
        """Check if message is from a group chat."""
        data = message_data.get('Data', {})
        from_user = data.get('FromUserName', {}).get('string', '')
        to_user = data.get('ToUserName', {}).get('string', '')
        return '@chatroom' in from_user or '@chatroom' in to_user

    def _extract_at_mentions(
        self,
        message_data: Dict[str, Any]
    ) -> List[str]:
        """Extract list of @ mentioned wxids from message."""
        data = message_data.get('Data', {})
        msg_source = data.get('MsgSource', '')

        if not msg_source:
            return []

        try:
            root = ET.fromstring(msg_source)
            atuserlist_elem = root.find('atuserlist')
            if atuserlist_elem is not None and atuserlist_elem.text:
                ats = atuserlist_elem.text.strip(',').split(',')
                return [wxid for wxid in ats if wxid]
        except ET.ParseError:
            pass

        return []

    def _is_bot_mentioned(
        self,
        message_data: Dict[str, Any],
        text_content: str
    ) -> bool:
        """Check if bot is @mentioned in group chat message."""
        data = message_data.get('Data', {})
        msg_source = data.get('MsgSource', '')
        wxid = message_data.get('Wxid', '')

        if not wxid:
            return False

        if '@' not in text_content and not msg_source:
            return False

        try:
            if msg_source:
                root = ET.fromstring(msg_source)
                alnode = root.find('alnode')
                if alnode is not None:
                    fr_elem = alnode.find('fr')
                    if fr_elem is not None and fr_elem.text == '1':
                        return True

                at_mentions = self._extract_at_mentions(message_data)
                if wxid in at_mentions:
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

    async def download_and_send_images(
        self,
        app_id: str,
        to_wxid: str,
        image_urls: List[str]
    ) -> None:
        """Send images from URLs via WeChat. Gewe API accepts remote URLs directly."""
        for image_url in image_urls:
            try:
                await self.send_image_message(
                    app_id=app_id,
                    to_wxid=to_wxid,
                    img_url=image_url
                )
                logger.info("Successfully sent image from URL: %s", image_url)
            except Exception as e:
                logger.error("Failed to send image %s: %s", image_url, e)

    async def process_incoming_message(
        self,
        message_data: Dict[str, Any]
    ) -> Tuple[Optional[str], List[str], Optional[str], Optional[str], Optional[Dict[str, Any]]]:
        """
        Process incoming WeChat message and generate Dify response.

        Returns:
            Tuple of:
            - response_text: Dify response text (with images removed)
            - image_urls: List of image URLs from Dify response
            - to_wxid: Recipient wxid
            - sender_wxid: Original sender wxid (for @ mentions in group chats)
            - quoted_message: Quoted message dict (if present)
        """
        try:
            wxid = message_data.get('Wxid', '')
            app_id = message_data.get('Appid', '')
            data = message_data.get('Data', {})
            from_user = data.get('FromUserName', {}).get('string', '')
            to_user = data.get('ToUserName', {}).get('string', '')
            msg_id = data.get('NewMsgId') or data.get('MsgId', 0)
            msg_type = data.get('MsgType', 0)

            # Extract quoted message if present
            quoted_message = self._extract_quoted_message(message_data)

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
                return None, [], None, None, None

            logger.info("Processing incoming message from %s: %s", from_user, text_content[:50])

            dify_client = self._get_dify_client()
            dify_user_id = f"gewe_{wxid}"

            is_group_chat = self._is_group_chat_message(message_data)

            # Extract sender wxid for group messages (for @ mentions)
            sender_wxid_for_at = None
            if is_group_chat:
                response_to = to_user if '@chatroom' in to_user else from_user
                conversation_id = f"gewe_{wxid}_{response_to}"

                data = message_data.get('Data', {})
                content = data.get('Content', {}).get('string', '')
                if ':\n' in content:
                    parts = content.split(':\n', 1)
                    if len(parts) > 1:
                        sender_wxid_for_at = parts[0]
            else:
                response_to = from_user
                conversation_id = f"gewe_{wxid}_{from_user}"

            # Build message with quoted context if present
            if quoted_message:
                quoted_content = quoted_message.get('content', '')
                quoted_nickname = quoted_message.get('nickname', '')
                if quoted_content:
                    formatted_message = (
                        f"{text_content}\n\n"
                        f"[回复: @{quoted_nickname}: {quoted_content}]"
                    )
                else:
                    formatted_message = text_content
            else:
                formatted_message = text_content

            response = await dify_client.chat_blocking(
                message=formatted_message,
                user_id=dify_user_id,
                conversation_id=conversation_id,
                auto_generate_name=False
            )

            answer = response.get('answer', '')
            if not answer:
                logger.warning("Dify returned empty answer")
                return None, [], None, None, None

            # Parse markdown images from Dify response
            text_content, image_urls = self._parse_markdown_images(answer)

            # Check for files field in response (future support)
            files = response.get('files', [])
            if files:
                for file_id in files:
                    try:
                        file_url = await dify_client.get_file_preview_url(file_id)
                        image_urls.append(file_url)
                    except Exception as e:
                        logger.warning("Failed to get file preview URL for %s: %s", file_id, e)

            logger.info(
                "Generated Dify response - Text length: %d, Images: %d",
                len(text_content) if text_content else 0,
                len(image_urls)
            )

            return text_content, image_urls, response_to, sender_wxid_for_at, quoted_message

        except Exception as e:
            logger.error("Error processing incoming message: %s", e, exc_info=True)
            return None, [], None, None, None
