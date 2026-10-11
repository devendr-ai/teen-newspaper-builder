# Architecture

```
editions/<id>/edition.yaml   ─┐
editions/<id>/issues/*.json  ─┼─►  ygc.checks  ─►  ygc.render  ─►  PDF + page PNGs
docs/CRAFT_RULES.md          ─┘        │
                                       └─► ygc.prompt  ─►  editions/<id>/PROMPT.md
```

| Module | Responsibility |
|---|---|
| `ygc/edition.py` | Load `edition.yaml`, merge defaults, validate with readable errors. |
| `ygc/render.py` | Turn a page plan into frames; render blocks; `measure()` lays out each column with the same engine as the build and reports exact free/over points. |
| `ygc/graphics.py` | Map, bar chart, illustration motifs. Unchanged from template v3. |
| `ygc/styles.py` | Paragraph styles, scaled by `type_scale` (1.0 = template v3 exactly). |
| `ygc/checks.py` | Every machine-checkable rule, driven by the edition. |
| `ygc/prompt.py` | Generates each edition's AI prompt from its YAML plus the craft rules. |
| `ygc/skeleton.py` | Empty, correctly shaped issue for an edition. |
| `ygc/migrate.py` | Converts template-v3 issue files. |
| `ygc/__main__.py` | The `python -m ygc` command line. |

## Design decisions

**Content and identity are data.** Pages, columns, sections, desks, reader,
purpose, cadence and labels all live in YAML. Python only knows how to draw
block *types*.

**Columns are independent frames.** Content never flows from one column into
the next, so a long story can't silently push the sign-off onto an extra page.
`measure()` makes overflow an exact, located error before the PDF is built.

**Fit is measured, not counted.** Template v3 used per-field character budgets
tuned for one layout. Measuring real line breaks works for any page plan, type
size and column count without re-tuning.

**The prompt is a build product.** It is generated from the edition and the
craft rules, and the tests fail if a committed `PROMPT.md` is stale, so the AI
instructions can never drift from the configuration.

**Backward compatibility is tested.** The `young-global-citizen` edition renders
issues pixel-identical to template v3.
