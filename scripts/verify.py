"""Exercise the actual Docker/MCP workflow and write a compact evidence report.

This executable walkthrough is not a unit-test suite. It requires a running lab.
"""

import asyncio
import json
import subprocess
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.shared.exceptions import McpError

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / ".local"
COMPOSE = ["docker", "compose", "--project-directory", str(ROOT)]
EXPECTED = {"web": {"page_outline"}, "backend": {"order_summary", "release_preview"}}


def run(*args):
    result = subprocess.run(
        args, check=False, capture_output=True, text=True, timeout=120
    )
    if result.returncode:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {args}\n{result.stderr.strip()}"
        )
    return result.stdout.strip()


def cli(service, *args):
    return run(*COMPOSE, "run", "--rm", "-T", "--no-deps", service, *args)


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def containers():
    ids = run(
        "docker",
        "ps",
        "-q",
        "--filter",
        "label=io.github.mcp-profiles-lab.component=tool-server",
    ).split()
    if not ids:
        return []
    raw = json.loads(run("docker", "inspect", *ids))
    return [
        {
            "id": c["Id"],
            "image": c["Config"]["Image"],
            "user": c["Config"]["User"],
            "memory": c["HostConfig"]["Memory"],
            "nano_cpus": c["HostConfig"]["NanoCpus"],
            "cap_drop": c["HostConfig"]["CapDrop"],
            "privileged": c["HostConfig"]["Privileged"],
            "mounts": [
                {"destination": m["Destination"], "rw": m["RW"]} for m in c["Mounts"]
            ],
        }
        for c in raw
    ]


@asynccontextmanager
async def connect(role, service="toolkit"):
    server = StdioServerParameters(
        command=str(ROOT / "scripts/gateway.sh"), args=[role, service]
    )
    with (OUTPUT / f"{service}-{role}.log").open("w") as log:
        async with stdio_client(server, errlog=log) as (read, write):
            async with ClientSession(
                read, write, read_timeout_seconds=timedelta(seconds=60)
            ) as session:
                await session.initialize()
                yield session


def payload(result):
    require(not result.isError, f"Tool error: {result}")
    return json.loads(next(item.text for item in result.content if item.type == "text"))


async def main(report):
    report["before"] = containers()
    require(not report["before"], "Close other lab clients before verifying lifecycle")
    async with connect("web") as web, connect("backend") as backend:
        for role, client in [("web", web), ("backend", backend)]:
            names = {tool.name for tool in (await client.list_tools()).tools}
            require(names == EXPECTED[role], f"Unexpected {role} tool set: {names}")
        report["checks"].append(
            "PASS: simultaneous clients see only their profile's tools."
        )
        report["after_discovery"] = containers()
        outline = payload(
            await web.call_tool(
                "page_outline",
                {"html": "<h1>Docker <em>MCP</em></h1><h2>Profiles</h2>"},
            )
        )
        require(
            outline
            == {
                "headings": [
                    {"level": 1, "text": "Docker MCP"},
                    {"level": 2, "text": "Profiles"},
                ],
                "count": 2,
            },
            "Wrong outline",
        )
        summary = payload(await backend.call_tool("order_summary", {"region": "west"}))
        require(
            summary == {"region": "west", "orders": 2, "total_cents": 3750},
            "Wrong order summary",
        )
        report["checks"].append(
            "PASS: HTML outline and SQLite order summary return the expected results."
        )
        denied = await backend.call_tool(
            "release_preview", {"environment": "production"}
        )
        require(
            denied.isError and "Lab policy" in str(denied),
            "Production call was not intercepted",
        )
        allowed = payload(
            await backend.call_tool("release_preview", {"environment": "staging"})
        )
        require(
            allowed["changes_applied"] is False and allowed["environment"] == "staging",
            "Staging preview failed",
        )
        invalid = await backend.call_tool("order_summary", {"region": "invalid"})
        require(invalid.isError, "Invalid region was accepted")
        oversized = await web.call_tool("page_outline", {"html": "x" * 65537})
        require(oversized.isError, "Oversized HTML was accepted")
        try:
            unknown = await web.call_tool("order_summary", {"region": "west"})
        except McpError as error:
            require(error.error.code == -32602, f"Unexpected protocol failure: {error}")
        else:
            require(unknown.isError, "Web profile accessed a backend tool")
        report["checks"].append(
            "PASS: interceptor blocks production and allows staging; invalid, oversized and cross-profile calls fail."
        )
        report["during"] = containers()
        require(len(report["during"]) == 2, "Expected two tool containers")
        for c in report["during"]:
            require(
                c["user"] == "10001:10001" and not c["privileged"],
                "Tool user/privileges differ",
            )
            require(
                c["memory"] == 256 * 1024 * 1024 and c["nano_cpus"] == 1000000000,
                "Resource limits differ",
            )
            require(
                not any(m["destination"].endswith("docker.sock") for m in c["mounts"]),
                "Tool received Docker socket",
            )
        report["checks"].append(
            "PASS: both tool containers run non-root, unprivileged, with 1 CPU / 256 MiB and no Docker socket."
        )
    for _ in range(30):
        report["after"] = containers()
        if not report["after"]:
            break
        await asyncio.sleep(1)
    require(not report["after"], "Tool containers survived gateway disconnect")
    report["checks"].append(
        "PASS: tool containers are removed after both clients disconnect."
    )

    # Publish profiles as actual OCI artifacts, then pull into a different database.
    # The registry shares localhost with CLI containers and has no published host port.
    for role in ("web", "backend"):
        ref = f"localhost:5000/profiles/{role}:v1"
        report.setdefault("oci", {})[role] = cli(
            "toolkit", "profile", "push", f"lab_{role}", ref
        )
        existing = json.loads(cli("teammate", "profile", "list", "--format", "json"))
        for p in existing:
            if p["id"] == f"lab_{role}":
                cli("teammate", "profile", "remove", p["id"])
        cli("teammate", "profile", "pull", ref)
        original = json.loads(
            cli("toolkit", "profile", "show", f"lab_{role}", "--format", "json")
        )
        imported = json.loads(
            cli("teammate", "profile", "show", f"lab_{role}", "--format", "json")
        )
        require(
            original["servers"] == imported["servers"], "OCI round-trip changed servers"
        )
        async with connect(role, "teammate") as client:
            names = {t.name for t in (await client.list_tools()).tools}
            require(names == EXPECTED[role], "Imported tool set differs")
            result = (
                await client.call_tool("page_outline", {"html": "<h1>Shared</h1>"})
                if role == "web"
                else await client.call_tool("order_summary", {"region": "all"})
            )
            require(not result.isError, "Imported profile tool call failed")
    require(not containers(), "Imported-profile containers survived disconnect")
    report["checks"].append(
        "PASS: both OCI profiles push/pull into a separate database and execute successfully."
    )


if __name__ == "__main__":
    OUTPUT.mkdir(exist_ok=True)
    report = {
        "started_at": datetime.now(UTC).isoformat(),
        "source_commit": run("git", "-C", str(ROOT), "rev-parse", "HEAD")
        if (ROOT / ".git").exists()
        else None,
        "checks": [],
        "status": "failed",
    }
    started = time.monotonic()
    try:
        asyncio.run(main(report))
        report["status"] = "passed"
    except BaseException as error:
        report["error"] = str(error)
        raise
    finally:
        report["duration_seconds"] = round(time.monotonic() - started, 2)
        (OUTPUT / "verification.json").write_text(json.dumps(report, indent=2) + "\n")
        print("\n".join("- " + check for check in report["checks"]))
        print(f"Result: {report['status']}. Evidence: .local/verification.json")
