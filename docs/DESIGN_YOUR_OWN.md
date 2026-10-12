# Design your own: a paper written by the parent's chatbot

The website's **Design your own** page (`builder.html`, built from
`tools/builder/`) lets a parent make a paper nobody else gets, without an API
key and at no cost to the site:

1. They choose the reader, the kind of paper, how it should feel, interests,
   learning sections, length and frequency. The proof on the right shows every page.
2. **Copy instructions** puts the paper's full instructions on the clipboard. They
   are the same instructions the daily pipeline uses (`ygc/prompt.py`), written
   for a chatbot: today's date and the issue number are stated, the chatbot must
   search the web and refuse rather than write from memory, and it replies with
   one JSON code block.
3. They paste the instructions into ChatGPT, Claude or Gemini with web search on.
4. They paste the chatbot's reply back. A story or section that runs a little
   long is trimmed the way a sub-editor would: whole sentences from its end, up
   to about a third of the column's writing, never headlines, boxes or quizzes;
   the page says what it cut. Then it checks the paper with the same checks as
   every published issue (sections, sources, printable characters, every column
   measured) and builds the same PDF. If something still fails, it shows a fix
   list to paste back to the chatbot. If columns have a lot of empty space, it offers an
   optional "make it fuller" request.
5. For ages 6–8 the page also makes the Big Question poster the same way.

## How it works

Everything runs in the visitor's browser. The page loads Python
([Pyodide](https://pyodide.org), from the jsDelivr CDN) and `builder-engine.zip`,
which the site build writes next to `builder.html` (`ygc.site.engine_zip`: the
`ygc` package, `docs/CRAFT_RULES.md`, `docs/POSTERS.md` and the pure-Python
ReportLab the engine draws with). The edition file the builder generates is
installed into the browser's memory and handled by `ygc/chat.py`:

| Function | What it does |
|---|---|
| `chat.install(yaml_text)` | Saves and validates the builder's edition file |
| `chat.instructions(ed, date, number)` | The chatbot instructions for one issue |
| `chat.check_paper(ed, reply, date, number)` | Reads the reply, trims overlong columns (`chat.fit`), runs every check, returns the fix list or the PDF |
| `chat.length_guide(ed)` / `chat.layout_problems(ed)` | Word budgets measured on the real layout, and layouts that can't fit at all |
| `chat.poster_instructions(ed, date)` / `chat.check_poster(ed, reply, date)` | The same for the Big Question poster |

Nothing a parent types is sent anywhere: the only downloads are Pyodide, its
packages and the engine. Issue numbers are kept in the browser's local storage
(one per paper per day).

## Limits

- The chatbot's sources are listed in the paper but not verified against what
  it actually read, unlike the daily pipeline's research pool. The page says so
  and asks parents to skim the paper.
- The first visit downloads about 15 MB (Python and the engine), which takes a
  few seconds; browsers cache it after that.
- Opening `tools/newspaper-builder.html` straight from disk shows the proof and
  the edition file, but copying instructions and printing need the page served
  over http with `builder-engine.zip` beside it (`python -m ygc site` builds both).
