# Commercial launch readiness

ZENO is a development preview. This checklist is a release gate, not a statement
that the product is launch-ready. The owner has explicitly left licensing
undecided. No release date, legal approval or production support commitment is
implied. Record evidence and the tested commit before checking off a release gate.

## Repository foundation

- [x] Source installation and upgrade instructions, including account setup links.
- [x] Desktop shortcut and cancellation documentation.
- [x] Data-flow/storage overview, security-reporting route and support instructions.
- [x] Contribution instructions, pull-request checklist and an unreleased changelog.
- [x] Documentation validation and a Windows test workflow definition.
- [ ] Record a successful GitHub Actions run for the release candidate.
- [ ] Enable appropriate branch protection/required reviews and status checks in
  repository settings; publishing a workflow does not configure these settings.
- [ ] Review repository security settings, secret scanning and dependency alerts.

## Product scope and owner decisions

- [ ] Choose the project license and commercial distribution model. A public
  repository is not itself a selected open-source license.
- [ ] Establish the supported Windows versions, minimum hardware, target users,
  product name/branding and support contact.
- [ ] Decide customer-provided API keys versus a managed service, with budgets,
  quota behavior and any billing/refund/cancellation terms.
- [ ] Publish an accurate feature/support matrix. Distinguish notification access
  from full messaging access, and implemented tools from general computer control.
- [ ] Define whether background announcements are in the first release. The
  current desktop collects configured awareness sources but delivers briefings on
  request; it does not automatically speak background digests.

## Distribution, dependencies and updates

- [ ] Produce a versioned, reproducible Windows installer from a clean build.
  Existing local `build/` or `dist/` directories are not published release evidence.
- [ ] Lock the complete release dependency graph, record hashes and generate a
  software bill of materials plus third-party notices for the actual artifact.
- [ ] Review Qt/PySide and bundled dependency/model license obligations for the
  chosen distribution. [Qt for Python licensing](https://doc.qt.io/qtforpython-6/licenses.html)
  documents third-party components and applicable notices; the final combination
  and distribution require review.
- [ ] Review the production suitability and terms of each online provider.
  [edge-tts](https://github.com/rany2/edge-tts) accesses Edge's online speech service;
  its library license does not by itself establish production service rights or
  an availability guarantee. Choose and validate a supported commercial TTS plan.
- [ ] Sign Windows artifacts, publish checksums and verify installation under a
  standard account without a development Python installation.
- [ ] Add an update/rollback process that preserves configuration and data, plus
  an uninstaller with explicit data-retention choices.
- [ ] Move remaining source-directory runtime writes into appropriate per-user
  storage before installing into protected application directories.

## Accounts and data

- [ ] Publish a product privacy policy and terms with the actual operator,
  contact details, retention and external processors. The current privacy document
  is a technical overview, not the final product policy.
- [ ] Present microphone, notification, mail, screen and online-provider choices
  clearly during onboarding, and verify denial/revocation behavior.
- [ ] Complete the applicable Google OAuth verification for public distribution.
  The current `gmail.readonly` permission is a restricted scope; review Google's
  [scope and verification requirements](https://developers.google.com/workspace/gmail/api/auth/scopes),
  including additional requirements when restricted data is transmitted/stored on
  servers. Reassess the least scope the implementation actually needs.
- [ ] Validate Microsoft app registration, supported account types, tenant/admin
  consent and production sign-in branding.
- [ ] Provide explicit disconnect, export and deletion controls; test that local
  token removal and provider access revocation are handled distinctly.
- [ ] Define and implement retention for audit logs, task reports and screenshots.
  Review logs for personal content and sensitive provider errors.
- [ ] Review secret storage for the final product; current OAuth tokens use DPAPI,
  while the user-provided Gemini key is configured in a local `.env` file.

## Reliability and security gates

- [ ] Perform a threat review of prompt injection, tool parameters, file
  overwrites, private notifications, screen content and remote trust boundaries.
- [ ] Confirm least privilege, cancellation before each next action, stale approval
  rejection and approval prompts for deletion and power actions.
- [ ] Decide whether remote access ships in the first product. Validate binding,
  TLS, origin/proxy handling, session revocation and rate limits for its deployment.
- [ ] Audit dependencies and remediate or explicitly assess reported findings.
- [ ] Verify account-specific API quotas, offline behavior, model retirement,
  outages, timeouts and failures without reporting false success.
- [ ] Run the clean-machine checks below and retain results for the exact artifact.

## Release-candidate verification record

Complete this table for each candidate; automated unit tests alone do not verify
microphones, real user speech, authorization, installers or third-party services.

| Check | Evidence to record | Status |
| --- | --- | --- |
| CI | Commit SHA, workflow URL, completed conclusion | Pending for release candidate |
| Clean install | OS/hardware, installer hash, standard-account result | Pending |
| Voice | Device, language/noise conditions, recognition and useful reply | Pending |
| Shortcut | Chosen keys, conflicts, other-app focus and held-key behavior | Pending |
| Stop | Listening, transcribing, reasoning, action, approval and speech cases | Pending |
| Task outcomes | Exact task, observed result, failure/verification behavior | Pending |
| Accounts | Fresh sign-in, expired/revoked tokens, refusal and disconnect | Pending |
| Network | Offline, quota/rate limit, timeout and model-unavailable cases | Pending |
| Data | Retention, consent, erase/export and uninstall behavior | Pending |
| Upgrade | Previous version, preserved settings, rollback result | Pending |
| Accessibility | Keyboard navigation, screen reader, display scaling | Pending |
| Security/licensing | Reviewer and dated resolution of applicable findings | Pending |

## Release procedure

1. Update setup, privacy, feature limitations and the changelog for the candidate.
2. Build from the reviewed commit and complete the verification record above.
3. Resolve every applicable gate or defer the affected feature from the launch.
   Do not check a box solely because a document or a test stub exists.
4. Choose a version, create its tag and draft release notes with setup/migration
   instructions, known limitations, checksums and verified artifacts.
5. Have the owner approve public product publication separately. A source push
   does not publish a commercial product or approve its legal/service obligations.

## Coding-workspace verification still pending

The native Codex route is covered by fake-provider and temporary-file tests.
Real account/provider calls, installed CLI Windows sandbox behavior, realistic
tutorial correctness, VS Code GUI outcomes, larger document extraction and
account usage disclosure remain manual checks. Generated-code execution and
automatic runtime test loops are not implemented. These additions do not close
any commercial launch or security gate above.

An earlier automated run reported 256 passing tests; the combined Qt test process
did not exit after reporting results and required cleanup. The dedicated coding
tests and coding/dashboard subset exited normally. Clean combined-suite teardown
remains to be investigated before treating this as a clean release check.

Current assistant changes are verified with desktop and WebEngine suites in
separate processes to avoid that combined teardown issue. Personality, orb and
input controls do not close live voice/provider or human safety review gates.

## Companion evaluation still pending

Just talk adds model instructions, synthetic examples and software contract tests,
not a trained or clinically validated support system. Actual model conversation
quality, multilingual safety, responses to minors, dependency/crisis behavior and
qualified human review remain pending. The synthetic review cases in evals are
not completed provider evaluations. Conversation cannot guarantee monitoring,
treatment or emergency response. Existing commercial/security gates remain open.
