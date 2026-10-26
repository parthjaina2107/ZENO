# Contributing

ZENO is a Windows development preview. Licensing is undecided; discuss substantial
external contributions with the maintainer before submitting them. Do not assume
a contribution agreement or distribution license has been established.

Use the [setup guide](docs/setup.md), then install development dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe scripts\check_docs.py
.\.venv\Scripts\python.exe -m pytest tests -q
```

Keep changes focused and include evidence for changes to task execution,
permissions, authentication, privacy and cancellation. Automated tests should mock
microphones, provider requests and OS mutations. Run hardware/live integration
checks deliberately and describe what they actually proved.

## Documentation is part of the change

- Update `docs/setup.md` whenever installation, dependencies, config, CLI,
  launchers, accounts, permissions, storage or upgrades change.
- Update `.env.example` without real values and revise affected feature guides.
- Add a changelog entry explaining user-visible changes and setup implications.
- If setup was reviewed and needs no update, explain why in the PR/changelog.
- Keep launch requirements and limitations accurate; a passing unit suite does
  not establish commercial, privacy, legal or service readiness.

CI checks local Markdown links, required documents, accidentally tracked sensitive
runtime paths and whether setup-impacting changes include setup/changelog review.
The check is a guardrail; it cannot validate every instruction's meaning.

Open a pull request with the problem, resulting behavior, relevant tests and setup
changes. Never attach unredacted logs, account tokens, private files or screenshots.
Use [SECURITY.md](SECURITY.md) for vulnerabilities and [SUPPORT.md](SUPPORT.md) for bugs.
