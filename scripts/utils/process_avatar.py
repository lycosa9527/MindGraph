"""
Script to process avatars for web usage.
Creates optimized versions at different sizes for all images.
Source file locations:
  - static/avatars/mindmate-source.png
  - static/avatars/mindgraph-source.png
  - static/avatars/debateverse-source.png
  - static/avatars/qwen-source.png
  - static/avatars/deepseek-source.png
  - static/avatars/doubao-source.png
  - static/avatars/kimi-source.png
  - static/avatars/judge-source.png
  - static/avatars/user-source.png
"""
from pathlib import Path

from PIL import Image


def process_image(source_path: Path, assets_dir: Path, output_configs: dict, name: str):
    """Process a source image and create optimized web versions.

    Args:
        source_path: Path to the source image file
        assets_dir: Directory to save optimized images
        output_configs: Dict mapping filename to size
        name: Display name for logging
    """
    if not source_path.exists():
        print(f"Error: Source file not found: {source_path}")
        return False

    # Open the source image
    with Image.open(source_path) as img:
        print(f"\n{name}:")
        print(f"  Original size: {img.size}")
        print(f"  Original format: {img.format}")
        print(f"  Original mode: {img.mode}")

        # Convert to RGBA if needed (for transparency support)
        if img.mode != "RGBA":
            img = img.convert("RGBA")

        for filename, size in output_configs.items():
            output_path = assets_dir / filename

            # Resize with high-quality resampling
            resized = img.resize((size, size), Image.Resampling.LANCZOS)

            # Save as optimized PNG
            resized.save(output_path, "PNG", optimize=True)

            # Get file size
            file_size = output_path.stat().st_size
            print(f"  Created {filename}: {size}x{size}px, {file_size / 1024:.1f} KB")

    return True


def process_avatars():
    """Process MindMate avatar, MindGraph logo, and Debateverse avatar, creating optimized web versions."""
    project_root = Path(__file__).parent.parent
    avatars_dir = project_root / "static" / "avatars"
    assets_dir = project_root / "frontend" / "src" / "assets"

    # Ensure assets directory exists
    assets_dir.mkdir(parents=True, exist_ok=True)

    # MindMate avatar sizes (2x for retina displays)
    mindmate_sizes = {
        "mindmate-avatar-lg.png": 256,  # Large size for fullpage welcome (displays at 128px)
        "mindmate-avatar-md.png": 96,   # Medium size for chat messages (displays at 48px)
        "mindmate-avatar-sm.png": 64,   # Small size for header/inline (displays at 32px)
    }

    # MindGraph logo sizes (2x for retina displays)
    mindgraph_sizes = {
        "mindgraph-logo-lg.png": 256,  # Large size (displays at 128px)
        "mindgraph-logo-md.png": 192,  # Medium size for main display (displays at 96px)
        "mindgraph-logo-sm.png": 96,   # Small size (displays at 48px)
    }

    # Debateverse avatar sizes (2x for retina displays)
    debateverse_sizes = {
        "debateverse-avatar-lg.png": 256,  # Large size for fullpage welcome (displays at 128px)
        "debateverse-avatar-md.png": 96,   # Medium size for chat messages (displays at 48px)
        "debateverse-avatar-sm.png": 64,   # Small size for header/inline (displays at 32px)
    }

    # LLM avatar sizes for debate (used in debateverse) - 120px for debate avatars
    llm_avatar_size = 120  # Displays at 60px in debate interface

    # Process MindMate avatar
    mindmate_source = avatars_dir / "mindmate-source.png"
    process_image(mindmate_source, assets_dir, mindmate_sizes, "MindMate Avatar")

    # Process MindGraph logo
    mindgraph_source = avatars_dir / "mindgraph-source.png"
    process_image(mindgraph_source, assets_dir, mindgraph_sizes, "MindGraph Logo")

    # Process Debateverse avatar
    debateverse_source = avatars_dir / "debateverse-source.png"
    process_image(debateverse_source, assets_dir, debateverse_sizes, "Debateverse Avatar")

    # Process LLM avatars for debate
    qwen_source = avatars_dir / "qwen-source.png"
    process_image(qwen_source, assets_dir, {"qwen-avatar.png": llm_avatar_size}, "Qwen Avatar")

    deepseek_source = avatars_dir / "deepseek-source.png"
    process_image(deepseek_source, assets_dir, {"deepseek-avatar.png": llm_avatar_size}, "DeepSeek Avatar")

    doubao_source = avatars_dir / "doubao-source.png"
    process_image(doubao_source, assets_dir, {"doubao-avatar.png": llm_avatar_size}, "Doubao Avatar")

    kimi_source = avatars_dir / "kimi-source.png"
    process_image(kimi_source, assets_dir, {"kimi-avatar.png": llm_avatar_size}, "Kimi Avatar")

    # Process judge avatar
    judge_source = avatars_dir / "judge-source.png"
    process_image(judge_source, assets_dir, {"judge-avatar.png": llm_avatar_size}, "Judge Avatar")

    # Process user avatar
    user_source = avatars_dir / "user-source.png"
    process_image(user_source, assets_dir, {"user-avatar.png": llm_avatar_size}, "User Avatar")

    print("\nImage processing complete!")
    print(f"Files saved to: {assets_dir}")


if __name__ == "__main__":
    process_avatars()
