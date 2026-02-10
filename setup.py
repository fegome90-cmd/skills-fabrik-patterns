#!/usr/bin/env python3
"""Installation script for Skills-Fabrik Patterns plugin."""

from pathlib import Path
import subprocess
import sys


def main():
    plugin_root = Path(__file__).parent

    print("🔧 Installing Skills-Fabrik Patterns plugin...")

    # Install dependencies
    print("📦 Installing Python dependencies...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
        cwd=plugin_root,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print(f"❌ Failed to install dependencies:\n{result.stderr}")
        return 1

    print("✅ Dependencies installed successfully")

    # Make scripts executable
    print("🔐 Making scripts executable...")
    for script in (plugin_root / "scripts").glob("*.py"):
        script.chmod(0o755)

    print("✅ Installation complete!")
    print(f"\n📍 Plugin location: {plugin_root}")
    print("\n📝 Next steps:")
    print("   1. Add to ~/.claude/settings.json:")
    print('      "enabledPlugins": {"skills-fabrik-patterns@local": true}')
    print("   2. Restart Claude Code")

    return 0


if __name__ == "__main__":
    sys.exit(main())
