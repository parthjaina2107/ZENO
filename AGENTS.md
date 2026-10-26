# Repository instructions

## Keep setup current

When changing dependencies, supported platforms, configuration, CLI flags,
launchers, desktop controls, model setup, accounts, data locations or upgrade
behavior, review `docs/setup.md` and update the relevant steps in the same change.
Update `.env.example`, feature-specific guides and README links when affected.
Record user-visible changes and setup/migration implications in `CHANGELOG.md`.
If setup needs no change, record the reviewed reason in the pull request or
changelog. Do not leave instructions for a later follow-up.

`scripts/check_docs.py --base <ref>` checks that setup-impacting changes include
either the setup guide or a changelog review; it does not prove semantic accuracy.
Always review the documented commands against the implementation.

## Verification and release claims

Run `python scripts/check_docs.py` and tests appropriate to the change using the
project environment. Hardware/provider smoke checks are explicit manual checks;
do not make live OS changes, read inboxes or use paid APIs as an incidental unit test.
Preserve user changes and never commit credentials or runtime content.

Keep `docs/launch-readiness.md` honest. Do not describe the product as ready for
commercial launch, select a license, publish a product release, or mark pending
manual/security/provider checks complete without supporting evidence and authority.
Licensing is currently undecided at the owner's request.
