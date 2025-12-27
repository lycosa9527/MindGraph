"""
Captcha Endpoints
=================

CAPTCHA generation and verification endpoints:
- /captcha/generate - Generate captcha image
- verify_captcha_with_retry() - Helper function for captcha verification

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import asyncio
import base64
import logging
import os
import random
import uuid
from io import BytesIO
from typing import Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Header, Request, Response, status
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from models.messages import Messages, get_request_language, Language
from services.captcha_storage import get_captcha_storage
from services.redis_rate_limiter import check_captcha_rate_limit
from utils.auth import (
    CAPTCHA_SESSION_COOKIE_NAME,
    RATE_LIMIT_WINDOW_MINUTES,
    is_https
)

logger = logging.getLogger(__name__)

router = APIRouter()

# File-based captcha storage (works across multiple server instances)
captcha_storage = get_captcha_storage()

# Path to Inter fonts (already in project)
CAPTCHA_FONTS = [
    os.path.join('static', 'fonts', 'inter-600.ttf'),  # Semi-bold
    os.path.join('static', 'fonts', 'inter-700.ttf'),  # Bold
]

# Color palette for captcha characters (vibrant colors for better visibility)
CAPTCHA_COLORS = [
    '#E74C3C',  # Red
    '#F39C12',  # Orange
    '#F1C40F',  # Yellow
    '#27AE60',  # Green
    '#3498DB',  # Blue
    '#9B59B6',  # Purple
    '#E91E63',  # Pink
    '#16A085',  # Teal
]


def _generate_custom_captcha(code: str) -> BytesIO:
    """
    Generate custom captcha image with larger letters and different colors per character.
    
    Args:
        code: The captcha code string to render (4 characters)
        
    Returns:
        BytesIO object containing PNG image data
    """
    # Image dimensions - match CSS display size (140x50)
    width, height = 140, 50
    
    # Create image with white background
    image = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(image)
    
    # Load font (use bold font for better visibility)
    font_path = CAPTCHA_FONTS[1] if os.path.exists(CAPTCHA_FONTS[1]) else CAPTCHA_FONTS[0]
    try:
        # Font size proportional to image height (70% of height for good visibility)
        font_size = int(height * 0.7)  # 35px for 50px height
        font = ImageFont.truetype(font_path, font_size)
    except Exception:
        # Fallback to default font if custom font fails
        font = ImageFont.load_default()
        font_size = 24
    
    # Measure all characters first to calculate proper spacing
    char_widths = []
    char_bboxes = []
    
    for char in code:
        try:
            # Pillow 8.0+ method
            bbox = draw.textbbox((0, 0), char, font=font)
            char_width = bbox[2] - bbox[0]
            char_height = bbox[3] - bbox[1]
            char_bboxes.append(bbox)
        except AttributeError:
            # Fallback for older Pillow versions
            char_width, char_height = draw.textsize(char, font=font)
            char_bboxes.append((0, 0, char_width, char_height))
            char_width = char_width
            char_height = char_height
        
        char_widths.append(char_width)
    
    # Calculate total width needed and spacing
    total_char_width = sum(char_widths)
    padding = width * 0.08  # 8% padding on each side
    available_width = width - (padding * 2)
    spacing = (available_width - total_char_width) / (len(code) - 1) if len(code) > 1 else 0
    
    # Starting X position (left padding)
    current_x = padding
    
    # Vertical center of the image (where we want characters centered)
    image_center_y = height / 2
    
    # Draw each character with different color and slight rotation
    for i, char in enumerate(code):
        # Select color for this character
        color = CAPTCHA_COLORS[i % len(CAPTCHA_COLORS)]
        
        # Get character dimensions
        bbox = char_bboxes[i]
        char_width = char_widths[i]
        char_height = bbox[3] - bbox[1]
        
        # Calculate character center X position
        char_center_x = current_x + char_width / 2
        
        # Add slight random rotation for each character (-10 to +10 degrees)
        rotation = random.uniform(-10, 10)
        
        # Create a temporary image for this character (with padding for rotation)
        padding_size = max(char_width, char_height) * 0.6
        char_img_width = int(char_width + padding_size * 2)
        char_img_height = int(char_height + padding_size * 2)
        char_img = Image.new('RGBA', (char_img_width, char_img_height), (255, 255, 255, 0))
        char_draw = ImageDraw.Draw(char_img)
        
        # Draw character so its visual center is at the center of char_img
        text_x = char_img_width / 2 - bbox[0] - char_width / 2
        text_y = char_img_height / 2 - bbox[1] - char_height / 2
        char_draw.text((text_x, text_y), char, fill=color, font=font)
        
        # Rotate character around its center
        rotated_char = char_img.rotate(rotation, center=(char_img_width/2, char_img_height/2), expand=False)
        
        # Calculate paste position so the character's visual center aligns with image center
        paste_x = int(char_center_x - rotated_char.width / 2)
        paste_y = int(image_center_y - rotated_char.height / 2)
        
        # Ensure paste position is within image bounds
        if paste_x < 0:
            paste_x = 0
        elif paste_x + rotated_char.width > width:
            paste_x = width - rotated_char.width
            
        if paste_y < 0:
            paste_y = 0
        elif paste_y + rotated_char.height > height:
            paste_y = height - rotated_char.height
        
        # Paste rotated character onto main image
        image.paste(rotated_char, (paste_x, paste_y), rotated_char)
        
        # Move to next character position
        current_x += char_width + spacing
    
    # Add subtle noise lines for security (prevent OCR)
    for _ in range(5):
        x1 = random.randint(0, width)
        y1 = random.randint(0, height)
        x2 = random.randint(0, width)
        y2 = random.randint(0, height)
        noise_color = random.choice(['#E0E0E0', '#E8E8E8', '#F0F0F0'])
        draw.line([(x1, y1), (x2, y2)], fill=noise_color, width=1)
    
    # Add subtle random noise dots
    for _ in range(15):
        x = random.randint(0, width)
        y = random.randint(0, height)
        noise_color = random.choice(['#E0E0E0', '#E8E8E8'])
        draw.ellipse([x-1, y-1, x+1, y+1], fill=noise_color)
    
    # Apply very slight blur filter for anti-OCR
    image = image.filter(ImageFilter.SMOOTH)
    
    # Save to BytesIO
    img_bytes = BytesIO()
    image.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    
    return img_bytes


@router.get("/captcha/generate")
async def generate_captcha(
    request: Request, 
    response: Response,
    x_language: Optional[str] = Header(None, alias="X-Language")
):
    """
    Generate custom captcha image with larger letters and different colors per character
    
    Features:
    - Uses existing Inter fonts from project
    - Large font size (90px) for better readability
    - Each character has a different vibrant color
    - Generates distorted image with noise to prevent OCR bots
    - 100% self-hosted (China-compatible)
    - Rate limited: Max 30 requests per 15 minutes per session (browser cookie)
    
    Returns:
        {
            "captcha_id": "unique-session-id",
            "captcha_image": "data:image/png;base64,..." 
        }
    """
    # Get or create session token for rate limiting
    session_token = request.cookies.get(CAPTCHA_SESSION_COOKIE_NAME)
    
    if not session_token:
        session_token = str(uuid.uuid4())
        logger.debug(f"New captcha session created: {session_token[:8]}...")
    
    # Rate limit by session token (Redis-backed, shared across workers)
    is_allowed, rate_limit_error = check_captcha_rate_limit(session_token)
    if not is_allowed:
        logger.warning(f"Captcha rate limit exceeded for session: {session_token[:8]}...")
        accept_language = request.headers.get("Accept-Language", "")
        lang: Language = get_request_language(x_language, accept_language)
        error_msg = Messages.error("too_many_login_attempts", lang, RATE_LIMIT_WINDOW_MINUTES)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=error_msg
        )
    
    # Set session cookie (matches rate limit window duration)
    response.set_cookie(
        key=CAPTCHA_SESSION_COOKIE_NAME,
        value=session_token,
        httponly=True,
        secure=is_https(request),
        samesite="lax",
        max_age=RATE_LIMIT_WINDOW_MINUTES * 60  # 15 minutes
    )
    
    # Generate 4-character code
    chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    code = ''.join(random.choices(chars, k=4))
    
    # Generate custom captcha image
    data = _generate_custom_captcha(code)
    
    # Convert to base64 for browser display
    img_base64 = base64.b64encode(data.getvalue()).decode()
    
    # Generate unique session ID
    session_id = str(uuid.uuid4())
    
    # Detect user language from headers
    accept_language = request.headers.get("Accept-Language", "")
    lang: Language = get_request_language(x_language, accept_language)
    
    # Store code with expiration (5 minutes)
    success = captcha_storage.store(session_id, code, expires_in_seconds=300)
    if not success:
        logger.error(f"Failed to store captcha {session_id}: Redis unavailable")
        error_msg = Messages.error("captcha_generate_failed", lang)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_msg
        )
    
    logger.debug(f"Generated captcha: {session_id} for session: {session_token[:8]}...")
    
    return {
        "captcha_id": session_id,
        "captcha_image": f"data:image/png;base64,{img_base64}"
    }


def verify_captcha(captcha_id: str, user_code: str) -> Tuple[bool, Optional[str]]:
    """
    Verify captcha code (synchronous wrapper for storage layer).
    
    Note: Verification is CASE-INSENSITIVE for better user experience.
    
    Returns:
        Tuple of (is_valid: bool, error_reason: Optional[str])
        error_reason can be: "not_found", "expired", "incorrect", "database_locked", "error", or None if valid
    Removes captcha after verification (one-time use)
    """
    return captcha_storage.verify_and_remove(captcha_id, user_code)


async def verify_captcha_with_retry(
    captcha_id: str, 
    user_code: str, 
    max_endpoint_retries: int = 2
) -> Tuple[bool, Optional[str]]:
    """
    Verify captcha with endpoint-level retry for database lock errors.
    
    This provides an additional retry layer beyond storage-level retries (8 retries).
    Uses async sleep to avoid blocking the event loop.
    
    Args:
        captcha_id: Unique captcha identifier
        user_code: User-provided captcha code
        max_endpoint_retries: Maximum endpoint-level retries (default: 2)
    
    Returns:
        Tuple of (is_valid: bool, error_reason: Optional[str])
        error_reason can be: "not_found", "expired", "incorrect", "database_locked", "error", or None if valid
    """
    for attempt in range(max_endpoint_retries):
        captcha_valid, captcha_error = verify_captcha(captcha_id, user_code)
        
        if captcha_valid:
            return captcha_valid, captcha_error
        
        if captcha_error != "database_locked":
            return captcha_valid, captcha_error
        
        # Database lock error - retry with exponential backoff
        if attempt < max_endpoint_retries - 1:
            delay = 0.1 * (2 ** attempt)  # 0.1s, 0.2s
            logger.warning(
                f"[Auth] Database lock in verify_captcha, "
                f"endpoint retry {attempt + 1}/{max_endpoint_retries} after {delay}s delay. "
                f"Captcha ID: {captcha_id[:8]}..."
            )
            await asyncio.sleep(delay)
        else:
            logger.error(
                f"[Auth] Database lock persists after {max_endpoint_retries} endpoint retries. "
                f"Captcha ID: {captcha_id[:8]}..."
            )
            return False, "database_locked"
    
    return False, "database_locked"



