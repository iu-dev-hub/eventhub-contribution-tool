# EventHub Contribution Tool

A command line tool that grades students' contributions to the
[EventHub](https://github.com/iu-dev-hub/eventhub) course project, using data from
GitHub and Taiga.

It was written for the *Software Verification and Testing* course and is developed
with the same rules the students follow: every change starts with an issue, goes
through a pull request, and is checked by CI. Tests are written from the
requirements before the code.

## What it does

1. Reads the instructor's student list (name, role, e-mail or usernames).
2. Downloads pull requests, reviews and discussions from GitHub.
3. Reads user stories, tasks and issues from Taiga's CSV exports.
4. Links each student to their GitHub and Taiga accounts.
5. Scores each student with the weights of their role (Product Owner, Scrum Master,
   Back, Front, Testçi) and grades them against the median of the same role.
6. Prints a table with grades, warnings, unmatched students and accounts that belong
   to no student.

A student who cannot be linked to any account is shown as **UNMATCHED** instead of
silently getting zero, so the instructor can fix the student list.

## Installation

Requires Python 3.12 or newer.

```bash
git clone https://github.com/iu-dev-hub/eventhub-contribution-tool.git
cd eventhub-contribution-tool
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e .
```

## Usage

All real data goes into the `data/` folder, which is never committed.

```bash
CONTRIBUTION_TOOL_TOKEN="github_pat_..." contribution-tool \
    --students data/ogrenciler.csv \
    --taiga data/taiga \
    --start 2026-09-21 --end 2026-10-19 \
    --role rol_d1
```

| Option | Required | Description |
|---|---|---|
| `--students` | yes | Student list CSV (see below) |
| `--taiga` | no | Folder with `userstories.csv`, `tasks.csv` and `issues.csv` |
| `--repo` | no | GitHub repository, default `iu-dev-hub/eventhub` |
| `--start`, `--end` | no | Date range, `YYYY-MM-DD`; both days are included, in Turkey time |
| `--role` | no | Role column to use, e.g. `rol_d2`; default is the first `rol*` column |
| `--factor` | no | Role target factor, default `1.0` (the median student gets 100) |
| `--adjustments` | no | Instructor adjustments CSV (see below) |
| `--no-taiga-history` | no | Use only the Taiga CSV exports, without logging in to Taiga |

Run `contribution-tool --help` for the full list.

### Student list

A CSV file with an `ad_soyad` column, one or more role columns starting with `rol`,
and any number of columns with e-mail addresses or usernames:

```csv
ad_soyad,rol_d1,rol_d2,rol_d3,eposta,github
Test Öğrenci Bir,PO,Back,Testçi,bir@example.org,ogrencibir
```

Values containing `@` are treated as e-mails, other values as usernames. Roles can be
written as `PO`, `SM`, `Back`, `Front`, `Testçi` (or `QA`); `Dev` counts as `Back`.

### Taiga exports

In Taiga, open **Settings → Project → Reports** and download the CSV files for user
stories, tasks and issues. Save them as `userstories.csv`, `tasks.csv` and
`issues.csv` in one folder.

### Taiga login

Taiga's CSV export does not show who changed a status, so a tester who moves stories
to Done would be invisible. When `--taiga` is given, the tool also downloads the change
history of each item. The project is private, so the tool logs in with your Taiga
account at every run:

```bash
CONTRIBUTION_TOOL_TAIGA_USERNAME="your-taiga-username" contribution-tool ...
```

The password is asked on screen without being shown, and is never stored. If you sign
in to Taiga with GitHub, set a password in your Taiga profile first. Use
`--no-taiga-history` to skip this step.

### Instructor adjustments

Some work leaves no trace in GitHub or Taiga. The instructor can add or subtract points
with a written reason, in a separate file such as `data/duzeltmeler.csv`:

```csv
ad_soyad,puan,gerekce
Test Öğrenci Bir,+10,"Backlog was created by the Scrum Master, PO led the team"
```

Points must be whole numbers. Put a reason that contains a comma in quotes. Run the
tool with `--adjustments data/duzeltmeler.csv`; the report shows each adjustment and
its reason next to the grade, and the final grade stays between 0 and 100.

### GitHub token

The tool needs a GitHub token with **read-only** access to public repositories:
GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens.

The token is read from the `CONTRIBUTION_TOOL_TOKEN` environment variable. Write it in
front of the command, as above, instead of using `export`, so it does not stay in your
shell. The tool does not use `GITHUB_TOKEN`, because git and gh also use it.

## Privacy

- The student list, Taiga exports and output files contain personal data. Keep them
  in `data/`; it is listed in `.gitignore`.
- Never commit a token. A test fails if a GitHub token appears in the source code.
- All test data in this repository is made up and uses `example.org` addresses.

## Project documents

- [Requirements](docs/requirements.md): every requirement has an ID (REQ-x.y)
- [Test plan](docs/test-plan.md): test levels, techniques, risks and the
  traceability table from requirements to tests

## Development

```bash
pip install -e ".[dev]"
pre-commit install        # once per clone: runs ruff before every commit
pytest
ruff check .
ruff format --check .
```

The ruff version is pinned in `pyproject.toml` and in `.pre-commit-config.yaml`.
When you update it, change both, so that your computer, the hook and CI use the same
version.

Workflow:

1. Open an issue with acceptance criteria.
2. Create a branch: `feat/12-short-name`, `fix/...`, `docs/...` or `chore/...`.
3. Write the test first and see it fail with `pytest`; then write the code. Update
   `docs/requirements.md` in the same change if a requirement changes.
4. Check and commit everything in one step:

   ```bash
   ruff format . && ruff check --fix . && pytest && git add -A && git commit -m "feat: ..."
   ```

5. Open a pull request with the template; merge with squash when CI passes.

Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/)
in English, e.g. `feat: match students to Taiga accounts`.

## License

[MIT](LICENSE)
