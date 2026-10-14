# Read & Play: the children's side of the site

The newsstand is for grown-ups: choose a paper, download it, print it. **Read &
Play** (`/play/` on the site, built by `ygc/play.py` as part of `python -m ygc
site`) is for the child, on a tablet or phone, from the same issue files.

- **Who's reading?** The lobby asks the child's age (6–8, 9–11, 12–14, 15+) and
  shows that age's papers, each with **Read** and **Play**. The choice is
  remembered on the device.
- **Read.** Each of the last 7 issues of every paper becomes a page. For ages
  6–11 it shows one story per screen (swipe, or Next and Back); older readers
  scroll. Every story and section has **Read it to me**, which uses the device's
  own voice and lights up each sentence as it's read. New words from the issue
  are underlined; tapping one shows its meaning and how it's used today, and can
  say it aloud. Text size, night mode and reading speed are remembered on the
  device. Pictures (maps, illustrations and charts) are drawn by the engine, the
  same as in the PDF. Sources sit behind **For grown-ups**.
- **Play.** *Word match*: tap a word, then its meaning. Papers without new words
  get *Story match*: tap a headline, then the sentence that starts its story. No
  timer and no losing; stars are kept on the device.

Nothing is tracked and nothing leaves the device. The quiz and fact-or-fiction
games come next, from a `play` section the papers will write alongside each issue.
