# Validation notes

Validated on November 1, 2026 using Docker Desktop 4.62.0, Engine 29.2.1,
Linux ARM64 containers on macOS, Python 3.12, MCP Python SDK 1.26.0, and the
pinned Docker MCP Gateway v0.44.3 image.

- **Pass:** web and backend clients expose different tool sets and return the
  expected HTML headings and SQL totals. Claude Code also called the web tool
  through the gateway and returned the expected result.
- **Pass:** the interceptor blocks production previews and allows staging;
  invalid inputs, oversized HTML, and cross-profile tool calls are rejected.
- **Pass:** real tool containers run non-root and unprivileged, with 1 CPU and
  256 MiB limits, no Docker socket mount, and removal on client disconnect.
- **Pass:** both profiles round-trip through a local OCI registry into a separate
  profile database and run successfully after import.

The code review covered every authored Python and shell file, Dockerfile,
Compose configuration, profile, dependency specification, and README command.
Formatting and Python lint checks passed. SQL uses bound parameters; database
connections close after each call; policy failures do not silently allow calls;
management tools are disabled; cleanup is scoped to lab resources. Generated
client paths, run logs, and runtime artifacts are excluded from version control.

This is a tutorial, not a production security audit. The tools use fixtures and
perform no real deployments. OCI sharing was tested locally on one Docker engine,
not against a remote authenticated registry or a second machine. macOS ARM64 was
executed; Linux, Windows/WSL, other architectures, and other MCP clients were not.
No claim is made that the gateway blocks all egress or drops every Linux capability.

Reproduce with `scripts/setup.py` followed by `scripts/verify.py` using the virtual
environment described in the README. The verifier records the checked-out commit
in `.local/verification.json`. Claude Code is optional and uses the generated
`.local/claude.mcp.json`; the Python verification itself needs no model calls.
