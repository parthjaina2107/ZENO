# Security reporting

ZENO can change local files and system state. The current development preview has
not completed a product security audit, and no long-term supported release exists.
Use the latest reviewed source and treat all remote exposure deliberately.

Report vulnerabilities privately through the repository's **Security → Report a
vulnerability** route if available:

https://github.com/parthjaina2107/ZENO/security/advisories/new

If private reporting is unavailable, contact the maintainer through a channel
listed on their GitHub profile to arrange a private report. A dedicated product
security address and response policy remain launch checklist items. Do not post
exploit details, secrets or private user data in a public issue. No response-time
or bounty commitment is currently established.

Include the affected commit, Windows/Python versions, sanitized reproduction,
expected behavior, impact and any proposed fix. Do not send real API keys, OAuth
tokens, private messages, raw logs or screenshots containing personal information.

If a key/token is exposed, revoke or rotate it at the provider first. Removing a
file from the latest commit does not erase Git history or revoke credentials.
For local data locations and removal, see [privacy](docs/privacy.md).
