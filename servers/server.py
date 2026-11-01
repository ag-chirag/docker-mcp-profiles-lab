"""Two small, deterministic MCP servers for exploring Docker gateway profiles."""

import os
import sqlite3
from contextlib import closing
from html.parser import HTMLParser
from typing import Literal

from mcp.server.fastmcp import FastMCP

ROLE = os.environ["LAB_ROLE"]
if ROLE not in {"web", "backend"}:
    raise ValueError("LAB_ROLE must be web or backend")
mcp = FastMCP(f"profiles-lab-{ROLE}")


class PageOutline(HTMLParser):
    """Collect heading text without executing HTML or fetching URLs."""

    def __init__(self):
        super().__init__()
        self.headings = []
        self.current = None
        self.text = []

    def handle_starttag(self, tag, attrs):
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.current, self.text = tag, []

    def handle_data(self, data):
        if self.current:
            self.text.append(data)

    def handle_endtag(self, tag):
        if tag == self.current:
            self.headings.append(
                {"level": int(tag[1]), "text": "".join(self.text).strip()}
            )
            self.current = None


if ROLE == "web":

    @mcp.tool()
    def page_outline(html: str) -> dict:
        """Extract headings from supplied HTML; no network or filesystem access."""
        if len(html.encode("utf-8")) > 65536:
            raise ValueError("HTML must be at most 64 KiB")
        parser = PageOutline()
        parser.feed(html)
        parser.close()
        return {"headings": parser.headings, "count": len(parser.headings)}

else:

    @mcp.tool()
    def order_summary(region: Literal["all", "west", "east"] = "all") -> dict:
        """Summarize a tiny in-memory order fixture; amounts are integer cents."""
        with closing(sqlite3.connect(":memory:")) as db:
            db.execute("CREATE TABLE orders (region TEXT, cents INTEGER)")
            db.executemany(
                "INSERT INTO orders VALUES (?, ?)",
                [("west", 1250), ("west", 2500), ("east", 900)],
            )
            count, cents = db.execute(
                "SELECT COUNT(*), COALESCE(SUM(cents), 0) FROM orders "
                "WHERE ? = 'all' OR region = ?",
                (region, region),
            ).fetchone()
        return {"region": region, "orders": count, "total_cents": cents}

    @mcp.tool()
    def release_preview(environment: Literal["staging", "production"]) -> dict:
        """Return a fictional release plan. This tool never deploys anything."""
        return {
            "environment": environment,
            "action": "preview only",
            "changes_applied": False,
        }


if __name__ == "__main__":
    mcp.run(transport="stdio")
