# Coding workspaces

The native island and dashboard use a separately signed-in Codex CLI to read a
project/tutorial, propose code, apply approved files with backups, and request
VS Code to open. This route is independent of Gemini. No model training is needed.

## Setup and use

Install a current Codex CLI using its
[official guide](https://learn.chatgpt.com/docs/non-interactive-mode), then run
`codex login` and `codex login status`. The CLI must support
`exec --ignore-user-config --output-schema`. Account usage limits apply. ZENO does
not copy login tokens. Codex user configuration is ignored to avoid inheriting
hooks/connectors; its authentication storage remains in use.

Install VS Code normally. Windows user/system Code.exe locations are detected.
Optional `.env` settings: `CODING_CODEX_PATH` and `CODING_VSCODE_PATH` (actual
executables, not .cmd wrappers), `CODING_MODEL` (empty uses CLI default), and
`CODING_TIMEOUT_SECONDS` (30–3600 seconds, default 900).

For PDF tutorials install the optional reader:

```powershell
uv pip install --python .venv/Scripts/python.exe -r requirements-coding.txt
```

Text/Markdown/source need no extra reader; DOCX uses the standard library.
PDF extraction has no OCR. Images, equations and tables may not extract faithfully.
Restart desktop mode after updating. ZENO remains closed until you launch it:

```powershell
.\.venv\Scripts\python.exe main.py --desktop
```

Select **Coding task · Codex** in the native dashboard, enter the full project
folder, and ask `Read Tutorial 3 and implement its exercises in Python with
explanatory comments`. Put the tutorial and starter files together. From the
island, type or say:

```text
Open VS Code and write Tutorial 3 in "C:\Users\HP\OneDrive\Desktop\etc"
```

Or start with `Coding task: complete Tutorial 3`. Missing paths prompt a question;
named folders are not guessed. Model clarification preserves the request for
your next answer; `cancel` clears it. Typed paths are more reliable than speech.
This route is native desktop only; CLI/server/phone mode is unchanged. Ordinary
conversation still uses the existing provider.

Projects must be inside permitted Documents, Desktop, Downloads or repository
roots, including existing Desktop/Documents under configured OneDrive roots.
This does not permit an entire home folder or drive root.

## Workflow and limits

1. Consent is requested before reading/sending supported workspace context.
2. A temporary snapshot excludes common dependencies, `.git`, `.env*` files and
   named credential files. PDF/DOCX text is added as context. These filters are
   not a secret scanner: source can still contain private data.
3. Codex uses its read-only sandbox, high reasoning effort and JSON output schema.
   The prompt prohibits network use, outside-folder reads, installs and project
   execution. Prompts are not OS isolation; the CLI's sandbox controls apply.
   This is not a hardened runner for hostile projects.
4. File paths, before/after hashes and diff previews require approval through the
   existing two-confirmation high-risk workflow. Previews are truncated; the
   full local proposal path is shown for review before approval.
5. Paths, sizes, Python/JSON syntax and changes since snapshot are checked.
   Originals are backed up, saved bytes are compared by SHA-256, and VS Code is
   requested to open. Its GUI outcome is not verified.

Limits: 30 changed text files, 200 KB per source/output file, 8 MB source context,
5,000 encountered source entries; 30 documents, 10 MB per document, 100 PDF pages
and 2 MB extracted text. Choose a small exercise folder. Binary changes,
deleting/renaming files, installs, generated-code execution and automatic runtime
test/fix loops are not implemented. Suggested checks have **not** run. Static
syntax/read-back checks do not establish correctness; review and test the code.

Stop terminates proposal generation's process tree. A file batch already saving
drains before cancellation completes; Stop does not undo it. Failed batches attempt
to restore outputs still matching that batch's hashes, preserving concurrent edits.
Review the report after failure. If VS Code is missing, saved files remain in place.

## Data and troubleshooting

Runs persist in `%LOCALAPPDATA%\ZENO\coding_runs\<run-id>` by default, or
`ZENO_DATA_DIR/coding_runs`. They contain goals/paths, schemas, provider events,
full proposals, reports and original-file backups. Approval audit logs can contain
diff previews. Temporary snapshots are removed after planning. No automatic
retention cleanup exists. Remove only selected run directories to erase those
local copies; this does not erase saved projects or provider data. Never commit
or publicly share raw logs.

If planning fails, check `codex login status`, account usage, connectivity and the
run event log. Upgrade an outdated CLI through its supported install method.
Real provider calls, Windows sandbox behavior, realistic tutorial correctness and
VS Code GUI interaction remain manual checks. Tests use fake providers/temp files.
