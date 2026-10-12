# Run the website: every paper, published automatically

Once this is set up, every morning GitHub researches the news, writes every
paper that's due, checks each one, and publishes the passing PDFs to a
website. Visitors pick a paper and download today's issue. Nothing needs to be
installed on your computer.

**What it costs:** GitHub Pages and Actions are free for public repositories.
The AI is paid per use through your Claude API account. Expect very roughly
$3–6 on a typical day for the nine-paper catalog (about five papers are due
on an average day), so roughly $90–180 a month. Fewer or less frequent papers cost
proportionally less. Every run records its actual cost in `data/runs/`, and a
daily cap stops spending if a run goes over.

## One-time setup (about 20 minutes)

### 1. Put the repository on GitHub

Push this repository to GitHub as a **public** repository. Public is what
makes Pages and Actions free.

### 2. Let GitHub publish a website

**Settings → Pages → Build and deployment → Source: GitHub Actions.**

### 3. Let the daily job save new issues

**Settings → Actions → General → Workflow permissions → Read and write
permissions**, then **Save**.

### 4. Get a Claude API key

1. Sign in at [platform.claude.com](https://platform.claude.com), add a payment method, and create an API key.
2. Set a **monthly spend limit** in the Console's billing settings. It's a hard
   backstop that holds even if something in the workflow goes wrong.
3. Web search is on by default. If an administrator turned it off, turn it back on
   in the Console's settings, or research fails with a "web search is not enabled"
   error.

### 5. Give GitHub the key

**Settings → Secrets and variables → Actions → New repository secret**
- Name: `ANTHROPIC_API_KEY`
- Value: your key

### 6. Optional settings

Same page, **Variables** tab:

| Variable | Default | What it does |
|---|---|---|
| `YGC_DAILY_BUDGET` | `15` | Dollars per run. The run stops starting new work once it's reached. |
| `REVIEW_MODE` | off | `true` sends each day's papers as a pull request instead of publishing. Merge to publish. |
| `YGC_MODEL` | `claude-sonnet-5-5` | Which Claude model researches and writes. |

### 7. Name your site

Edit `site.yaml`: the site's `title` and `tagline`, `base_url`
(`https://<your-username>.github.io/<repo-name>/`), and a `contact` email for
corrections. A contact address matters on a news site, especially one for
children.

### 8. Do a dry run

**Actions → Publish today's papers → Run workflow**, tick **dry run**, and
run it. The log lists which papers are due today and an estimated cost. No
money is spent.

### 9. Publish one paper

Run it again, untick dry run, and type one id under **only**, for example
`young-global-citizen`. When it finishes, the job summary links to your
website. Download the PDF and read it properly.

### 10. Leave it running

The job runs by itself every day at 11:15 UTC (4:15 am Pacific, 4:45 pm in
India). Change the `cron` line in `.github/workflows/daily.yml` to move it.

## Day to day

- **Pause a paper:** set `automation: enabled: false` in its `edition.yaml`.
- **Hide a paper from the site:** add `listed: false` under `site:`.
- **Weekly papers** publish on the day named in `automation: weekday:`.
- **Posters:** papers with `automation: poster: true` also get that week's Big
  Question poster, written and checked after the issue passes. A failed poster
  is skipped; the paper still publishes. See [POSTERS.md](POSTERS.md).
- **Add a paper:** design it in the builder, save it as
  `editions/<id>/edition.yaml`, and add the `automation` and `site` sections
  (copy them from any catalog edition). It appears on the site at the next run.
- **Fix a published issue:** edit its JSON in `editions/<id>/issues/` and
  commit. The site redeploys on its own.
- **See what happened:** each run's `data/runs/<date>.json` lists every paper's
  result, repair rounds and cost. `data/pools/<date>.json` holds the verified
  research each paper was written from. Papers that failed also appear as
  warnings on the workflow run.

## How a paper gets published

1. **Research, once per desk.** Claude searches the news for each desk the
   due papers need (World, India, Science and so on), using the web search tool.
   Any fact whose cited page wasn't actually returned by a search is
   discarded, and any story left without a verified source is dropped.
2. **Writing.** Each paper is written from that shared research only, with its
   own reader, purpose and rules from `PROMPT.md`. It may not search on its own,
   so facts are consistent across papers.
3. **Checking and repair.** The same `check` you'd run by hand: required
   sections, layout fit, printable characters, no repeated vocabulary, sources
   from the research only. Errors go back to Claude to fix, up to four rounds.
4. **Fact-check.** A separate pass compares every claim with the research.
   Unsupported claims go back for repair.
5. **Publish or skip.** Only passing issues are saved and published. A paper
   that still fails is skipped for the day and reported, and its previous
   issue stays up.

## Honest limits

- **It can still be wrong.** The research step only keeps facts tied to pages
  it actually retrieved, and the fact-check catches claims the research doesn't
  support. But a source can be wrong, and a fact can be subtly misread. The site
  says it's AI-written and shows every source.
- **Start with review on.** For papers aimed at young children, set
  `REVIEW_MODE` to `true` for the first couple of weeks. Each morning brings
  one pull request; skim the PDFs and merge. Switch it off once you trust it.
- **Pushing to `main`** must be allowed for the bot. If you protect `main`,
  use review mode instead.
- **Breaking news moves.** Casualty figures and early reports change after
  publication. The issue reflects what the sources said that morning.
