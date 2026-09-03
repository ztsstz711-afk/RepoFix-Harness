# Security policy

RepoFix executes tests from a target repository. Treat unknown repositories as
untrusted input even when the Docker execution backend is enabled.

## Supported version

Security fixes are applied to the latest release and the `main` branch.

## Reporting a vulnerability

Open a GitHub issue with a minimal reproduction that uses dummy credentials and
non-sensitive data. Never include API keys, access tokens, private source code,
or raw traces containing confidential repository content.

## Current boundary

The Docker backend isolates pytest execution with no network, a read-only
workspace and root filesystem, dropped capabilities, no privilege escalation,
and bounded CPU, memory, and process counts. The Harness process and file tools
still run on the host. This project therefore does not claim to provide a full
operating-system sandbox.
