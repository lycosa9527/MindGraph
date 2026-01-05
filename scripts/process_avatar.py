"""
Script to process MindMate avatar source for web usage.
Creates optimized versions at different sizes for MindMate avatar.
Source file location: static/avatars/mindmate-source.png
"""
from pathlib import Path

from PIL import Image


def process_avatar():
    """Process MindMate avatar source and create optimized web versions."""
    project_root = Path(__file__).parent.parent
    source_path = project_root / "static" / "avatars" / "mindmate-source.png"
    assets_dir = project_root / "frontend" / "src" / "assets"

    # Ensure assets directory exists
    assets_dir.mkdir(parents=True, exist_ok=True)

    if not source_path.exists():
        print(f"Error: Source file not found: {source_path}")
        return

    # Open the source image
    with Image.open(source_path) as img:
        print(f"Original image size: {img.size}")
        print(f"Original format: {img.format}")
        print(f"Original mode: {img.mode}")

        # Convert to RGBA if needed (for transparency support)
        if img.mode != "RGBA":
            img = img.convert("RGBA")

        # Define output sizes (2x for retina displays)
        sizes = {
            "mindmate-avatar-lg.png": 256,  # Large size for fullpage welcome (displays at 128px)
            "mindmate-avatar-md.png": 96,   # Medium size for chat messages (displays at 48px)
            "mindmate-avatar-sm.png": 64,   # Small size for header/inline (displays at 32px)
        }

        for filename, size in sizes.items():
            output_path = assets_dir / filename
            
            # Resize with high-quality resampling
            resized = img.resize((size, size), Image.Resampling.LANCZOS)
            
            # Save as optimized PNG
            resized.save(output_path, "PNG", optimize=True)
            
            # Get file size
            file_size = output_path.stat().st_size
            print(f"Created {filename}: {size}x{size}px, {file_size / 1024:.1f} KB")

    print("\nAvatar processing complete!")
    print(f"Files saved to: {assets_dir}")


if __name__ == "__main__":
    process_avatar()
