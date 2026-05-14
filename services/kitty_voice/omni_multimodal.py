"""
Omni realtime **vision** path for Kitty (reference for product + bridge work).

**Client → server (WebSocket)**

1. Message ``{\"type\": \"append_image\", \"data\": \"<base64>\", \"format\": \"jpeg\"}`` (handler:
   :func:`services.kitty_voice.ws_append_image.kitty_ws_handle_append_image`).

2. Server validates size (``KITTY_WS_IMAGE_*`` in :mod:`services.kitty_voice.ws_guards`), decodes base64,
   sends short PCM silence preamble, calls ``OmniClient.append_image``, ``commit_audio_buffer``,
   ``create_response`` with a short Chinese instruction to summarize readable content.

3. Session flags ``pending_kitty_image_paragraph`` so the first non-empty **transcription** can be
   routed through ``process_paragraph_with_qwen_plus`` when applicable (long structured extraction).

**Desktop truth**

- Hub / ``kitty:live_spec`` updates follow normal ``patch_context`` / voice diagram sync; vision-derived
  diagram edits should go through the same bridge as paragraph flow when the canvas must change
  (see :mod:`services.kitty_voice.diagram_voice_hub_bridge`).

**Frontend**

- Image bytes: ``frontend`` composables ``useKittyAgent`` / ``compressImageForKitty`` (size limits aligned
  with server guards where possible).
"""

from __future__ import annotations

KITTY_OMNI_MULTIMODAL_NOTES_REVISION = 1

__all__ = ["KITTY_OMNI_MULTIMODAL_NOTES_REVISION"]
