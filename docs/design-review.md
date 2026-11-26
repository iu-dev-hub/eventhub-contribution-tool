# Design: qualitative review (v2)

## Goal

For each student: (a) where their contributions differ from what is expected,
(b) how this changed between role periods, (c) what to do better. Student texts never
leave the instructor's computer.

## Approach

1. **Evidence.** The collectors keep every contribution with its text and link.
2. **Expectation cards.** One card per contribution type (pull request, code review,
   bug report, user story, discussion post, Taiga comment), stored as TOML files in
   `cards/`. Each item has an id, a yes/no question, a source (EventHub rule or
   industry practice) and a tip.
3. **Small questions.** A local model (Ollama) reviews one contribution against one
   card and answers each item with met / not met / not applicable, as JSON. The
   contribution text is limited to 2,000 characters, so a 4,096-token context is enough.
4. **Cache.** Results are stored by content hash, card version and model name.
5. **Reports in code, not in the model.** Gaps, progress and tips are calculated in
   Python from the item results. Tips come from the cards, not from the model.
6. **Calibration.** The instructor labels 20–30 contributions by hand. The model is
   used only if its agreement with the instructor is above the threshold.

## Why small questions

A small local model is unreliable when asked to judge many contributions at once.
One contribution, one card, yes/no answers: this keeps each answer checkable and the
results repeatable.

## Modules

| Module | Responsibility |
|---|---|
| `evidence.py` | Contribution records with text and link |
| `cards.py` | Loading and validating expectation cards |
| `review/llm.py` | Ollama client with JSON output |
| `review/assess.py` | One contribution against one card |
| `review/cache.py` | Stored results |
| `review/summary.py` | Gaps, progress, tips |
| `review/report.py` | One Markdown file per student |
| `review/cli.py` | `contribution-review` command |

## Privacy

- The model runs locally; no student text is sent over the network.
- Cache and reports are stored in `data/`, which is never committed.
- Student texts are data: the model is told not to follow instructions inside them.
