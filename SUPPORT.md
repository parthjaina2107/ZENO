# Support

This is a development preview without a commercial support SLA. Start with the
[setup/troubleshooting guide](docs/setup.md), then the relevant
[desktop](docs/desktop.md), [awareness](docs/awareness.md) or
[conversation](docs/conversation.md) guide.

For a bug, open an issue with:

- Commit/version and Windows/Python versions.
- Interface used: desktop, CLI text/voice, or remote browser.
- Minimal harmless reproduction, expected result and observed result.
- Microphone/STT/TTS settings when relevant, without credentials.
- Whether a typed request also fails, and redacted error details if available.

`python main.py --doctor` checks setup without recording or reading mail. Review
its output before sharing it. Logs and reports can contain private task data;
provide a small redacted excerpt rather than uploading the full files.

Do not include `.env`, API keys, OAuth JSON/tokens, private mail/messages or personal
screenshots. Vulnerabilities belong in the private route in [SECURITY.md](SECURITY.md).
Feature proposals should explain the user problem, examples and any setup/data
implications; the maintainer can assess them against the launch roadmap.
