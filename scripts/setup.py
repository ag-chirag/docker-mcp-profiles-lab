"""Build the lab, import profiles, and generate an opt-in Claude Code config."""

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def compose(*args):
    subprocess.run(
        ["docker", "compose", "--project-directory", str(ROOT), *args], check=True
    )


if __name__ == "__main__":
    (ROOT / ".local/exports").mkdir(parents=True, exist_ok=True)
    compose("--profile", "build", "build", "web-image", "backend-image")
    compose("up", "-d", "--wait", "registry")
    for role in ("web", "backend"):
        compose(
            "run",
            "--rm",
            "-T",
            "--no-deps",
            "toolkit",
            "profile",
            "import",
            f"/lab/profiles/{role}.json",
        )
    config = {
        "mcpServers": {
            "profiles-web": {
                "type": "stdio",
                "command": str(ROOT / "scripts/gateway.sh"),
                "args": ["web"],
            }
        }
    }
    destination = ROOT / ".local/claude.mcp.json"
    destination.write_text(json.dumps(config, indent=2) + "\n")
    print(f"Ready. Claude config: {destination}")
    print("Explore: .venv/bin/python clients/explore.py backend")
