"""Document Cleaner Service for Knowledge Space.

Author: lycosa9527
Made by: MindSpring Team

Advanced text cleaning and normalization (like Dify's CleanProcessor).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Optional, Dict, Any
import logging
import re


logger = logging.getLogger(__name__)


class DocumentCleaner:
    """
    Document cleaner for text normalization and cleaning.

    Removes invalid characters, normalizes whitespace, and optionally
    removes URLs/emails while preserving markdown links/images.

    Singleton pattern: only one instance is created.
    """

    _instance: Optional['DocumentCleaner'] = None

    def __new__(cls):
        """Singleton pattern: return the same instance on every call."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @staticmethod
    def _remove_urls_emails_preserving_markdown(text: str) -> str:
        """
        Remove URLs and emails while preserving Markdown links and images.

        Args:
            text: Text to process

        Returns:
            Text with URLs/emails removed but markdown preserved
        """
        email_pattern = r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)"
        text = re.sub(email_pattern, "", text)

        markdown_link_pattern = r"\[([^\]]*)\]\((https?://[^)]+)\)"
        markdown_image_pattern = r"!\[.*?\]\((https?://[^)]+)\)"
        placeholders: list[tuple[str, str, str]] = []

        def replace_markdown_with_placeholder(match):
            link_text = match.group(1)
            url = match.group(2)
            placeholder = f"__MARKDOWN_PLACEHOLDER_{len(placeholders)}__"
            placeholders.append(("link", link_text, url))
            return placeholder

        def replace_image_with_placeholder(match):
            url = match.group(1)
            placeholder = f"__MARKDOWN_PLACEHOLDER_{len(placeholders)}__"
            placeholders.append(("image", "image", url))
            return placeholder

        text = re.sub(markdown_link_pattern, replace_markdown_with_placeholder, text)
        text = re.sub(markdown_image_pattern, replace_image_with_placeholder, text)

        url_pattern = r"https?://\S+"
        text = re.sub(url_pattern, "", text)

        for idx, (link_type, text_or_alt, url) in enumerate(placeholders):
            placeholder = f"__MARKDOWN_PLACEHOLDER_{idx}__"
            if link_type == "link":
                text = text.replace(placeholder, f"[{text_or_alt}]({url})")
            else:
                text = text.replace(placeholder, f"![{text_or_alt}]({url})")

        return text

    @staticmethod
    def clean(
        text: str,
        remove_extra_spaces: bool = True,
        remove_urls_emails: bool = False
    ) -> str:
        """
        Clean and normalize text content.

        Args:
            text: Text to clean
            remove_extra_spaces: Remove multiple consecutive spaces/newlines
            remove_urls_emails: Remove URLs and emails (preserves markdown links/images)

        Returns:
            Cleaned text
        """
        if not text:
            return text

        # Step 1: Remove invalid symbols and control characters
        text = re.sub(r"<\|", "<", text)
        text = re.sub(r"\|>", ">", text)
        text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F\xEF\xBF\xBE]", "", text)
        text = re.sub("\ufffe", "", text)

        # Step 2: Remove extra spaces (if enabled)
        if remove_extra_spaces:
            text = re.sub(r"\n{3,}", "\n\n", text)
            space_pattern = r"[\t\f\r\x20\u00a0\u1680\u180e\u2000-\u200a\u202f\u205f\u3000]{2,}"
            text = re.sub(space_pattern, " ", text)

        # Step 3: Remove URLs and emails (if enabled, but preserve markdown)
        if remove_urls_emails:
            text = DocumentCleaner._remove_urls_emails_preserving_markdown(text)

        return text

    @staticmethod
    def clean_with_rules(text: str, rules: Optional[Dict[str, Any]] = None) -> str:
        """
        Clean text with configurable rules (like Dify's process_rule).

        Args:
            text: Text to clean
            rules: Optional rules dict with 'pre_processing_rules' list
                   Each rule has 'id' and 'enabled' fields

        Returns:
            Cleaned text
        """
        if not text:
            return text

        # Default cleaning (always applied)
        text = DocumentCleaner.clean(text, remove_extra_spaces=False, remove_urls_emails=False)

        # Apply configurable rules
        if rules and "pre_processing_rules" in rules:
            pre_processing_rules = rules["pre_processing_rules"]

            remove_extra_spaces = False
            remove_urls_emails = False

            for rule in pre_processing_rules:
                if rule.get("enabled", False):
                    rule_id = rule.get("id", "")
                    if rule_id == "remove_extra_spaces":
                        remove_extra_spaces = True
                    elif rule_id == "remove_urls_emails":
                        remove_urls_emails = True

            # Apply enabled rules
            if remove_extra_spaces or remove_urls_emails:
                text = DocumentCleaner.clean(
                    text,
                    remove_extra_spaces=remove_extra_spaces,
                    remove_urls_emails=remove_urls_emails
                )

        return text


def get_document_cleaner() -> DocumentCleaner:
    """Get document cleaner singleton instance."""
    return DocumentCleaner()
