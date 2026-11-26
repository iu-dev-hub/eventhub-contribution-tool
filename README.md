# EventHub Contribution Tool

A command line tool that grades students' contributions to the
[EventHub](https://github.com/iu-dev-hub/eventhub) course project, using data from
GitHub and Taiga.

It was written for the *Software Verification and Testing* course and is developed
with the same rules the students follow: every change starts with an issue, goes
through a pull request, and is checked by CI. Tests are written from the requirements
before the code.

## What it does

1. Reads the instructor's student list (name, role, e-mail or usernames).
2. Downloads pull requests, reviews and discussions from GitHub.
3. Reads user stories, tasks and issues from Taiga's CSV exports, and downloads their
   change history from the Taiga API.
4. Links each student to their GitHub and Taiga accounts and reports anything that
   cannot be linked.
5. Scores each student with the weights of their role (Product Owner, Scrum Master,
   Back, Front, Testçi) and grades them against the median of the same role.
6. Prints a table with grades and warnings, and can save an Excel report with a
   guidance sheet.

## Setup on a new computer

Requires Python 3.12 or newer. Do these steps once on every computer.

### 1. Install

```bash
git clone https://github.com/iu-dev-hub/eventhub-contribution-tool.git
cd eventhub-contribution-tool
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pre-commit install
```

### 2. Data

All real data lives in the `data/` folder, which is never committed:

```
data/
├── ogrenciler.csv            student list
├── duzeltmeler_d1.csv        instructor adjustments (optional)
└── taiga/
    ├── userstories.csv
    ├── tasks.csv
    └── issues.csv
```

The folder contains personal data. Move it between computers only on a USB stick or an
encrypted channel, never by e-mail or a public sharing link.

### 3. GitHub token

Create a **read-only** token on GitHub: Settings → Developer settings → Personal access
tokens → Fine-grained tokens → Generate new token → Repository access: *Public
repositories*. Create a separate token for each computer, so a lost one can be revoked
alone.

Save it in a file outside the repository, readable only by you:

```bash
mkdir -p ~/.config/contribution-tool
nano ~/.config/contribution-tool/token        # paste the token, save
chmod 600 ~/.config/contribution-tool/token
```

On Windows the file is `%APPDATA%\contribution-tool\token`. For a single run you can
instead set `CONTRIBUTION_TOOL_TOKEN`, which wins over the file. The tool does not use
`GITHUB_TOKEN`, because git and gh also use it.

### 4. Taiga login

The Taiga project is private. The tool logs in with your Taiga account at every run to
download the change history (who moved a story to Done, who wrote comments). Set your
Taiga username or e-mail once:

```bash
echo 'export CONTRIBUTION_TOOL_TAIGA_USERNAME="your-taiga-username"' >> ~/.bashrc
source ~/.bashrc
```

The password is asked on screen at every run without being shown, and is never stored.
If you sign in to Taiga with GitHub, set a password in your Taiga profile first.

### 5. Check

```bash
contribution-tool --help
pytest
```

## Usage

```bash
contribution-tool \
    --students data/ogrenciler.csv \
    --taiga data/taiga \
    --start 2026-09-21 --end 2026-10-19 \
    --role rol_d1 \
    --adjustments data/duzeltmeler_d1.csv \
    --excel data/rapor_d1.xlsx
```

| Option | Required | Description |
|---|---|---|
| `--students` | yes | Student list CSV |
| `--taiga` | no | Folder with `userstories.csv`, `tasks.csv` and `issues.csv` |
| `--repo` | no | GitHub repository, default `iu-dev-hub/eventhub` |
| `--start`, `--end` | no | Date range, `YYYY-MM-DD`; both days are included, in Turkey time |
| `--role` | no | Role column to use, e.g. `rol_d2`; default is the first `rol*` column |
| `--factor` | no | Role target factor, default `1.0` (the median student gets 100) |
| `--adjustments` | no | Instructor adjustments CSV |
| `--excel` | no | Also save the report to an Excel file |
| `--no-taiga-history` | no | Use only the Taiga CSV exports, without logging in to Taiga |

### Student list

A CSV file with an `ad_soyad` column, one or more role columns starting with `rol`, and
any number of columns with e-mail addresses or usernames:

```csv
ad_soyad,rol_d1,rol_d2,rol_d3,eposta,github,taiga
Test Öğrenci Bir,PO,Back,Testçi,bir@example.org,ogrencibir,ogrencibir
```

Values containing `@` are treated as e-mails, other values as usernames. Write the
Taiga **username**, not the display name; it is in the profile address
`tree.taiga.io/profile/<username>`. Roles can be written as `PO`, `SM`, `Back`, `Front`,
`Testçi` (or `QA`); `Dev` counts as `Back`.

### Taiga exports

In Taiga, open **Settings → Project → Reports** and download the CSV files for user
stories, tasks and issues. Save them as `userstories.csv`, `tasks.csv` and `issues.csv`
in `data/taiga/`. Download them again before every run, so new items are included.

### Instructor adjustments

Some work leaves no trace in GitHub or Taiga. Add or subtract points with a written
reason:

```csv
ad_soyad,puan,gerekce
Test Öğrenci Bir,+10,"Backlog was created by the Scrum Master, PO led the team"
```

Points must be whole numbers. Put a reason that contains a comma in quotes. The report
shows each adjustment and its reason; the final grade stays between 0 and 100.

### Reading the warnings

| Warning | What to do |
|---|---|
| `not matched to any GitHub or Taiga account` | Add the student's usernames to the list |
| `no Taiga account found` / `no GitHub account found` | Check the list; the student may also have no activity there |
| `'...' in the student list matched no account` | Fix the value (often a display name instead of a username) |
| `Role '...' has only one student` | The grade compares the student only with themselves |

Accounts listed under "Active accounts not linked to any student" are yours or belong
to people who are not students; check them for students whose usernames are missing.

## Privacy

- The student list, Taiga exports, adjustments and reports contain personal data. Keep
  them in `data/`; it is listed in `.gitignore` and a test checks this.
- Never commit a token. A test fails if a GitHub token appears in the source code.
- All test data in this repository is made up and uses `example.org` addresses.

## Project documents

- [Requirements](docs/requirements.md): every requirement has an ID (REQ-x.y)
- [Test plan](docs/test-plan.md): test levels, techniques, risks and the traceability
  table from requirements to tests
- [Design of the qualitative review (v2)](docs/design-review.md)

## Development

```bash
pytest
ruff check .
ruff format --check .
```

The ruff version is pinned in `pyproject.toml` and in `.pre-commit-config.yaml`; when
you update it, change both.

Workflow:

1. Open an issue with acceptance criteria.
2. Create a branch: `feat/12-short-name`, `fix/...`, `docs/...` or `chore/...`.
3. Write the test first and see it fail with `pytest`; then write the code. Update
   `docs/requirements.md` in the same change if a requirement changes.
4. Check and commit everything in one step:

   ```bash
   ruff format . && ruff check --fix . && pytest && git add -A && git status --short && git commit -m "feat: ..."
   ```

5. Open a pull request with the template; merge with squash when CI passes.

## License

[MIT](LICENSE)
