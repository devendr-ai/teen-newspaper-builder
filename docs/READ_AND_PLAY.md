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
- **Play.** A menu of up to three games, each with stars kept on the device, no
  timer and no losing:
  - *Word match*: tap a word, then its meaning. Papers without new words get
    *Story match*: tap a headline, then the sentence that starts its story.
  - *Quiz*: one question per screen, three answers. A wrong answer shows the right
    one, why, and **Read it again**, which opens the story it came from. Ages 6–8
    can hear each question.
  - *Fact or fiction?*: a claim about the issue; tap **True** or **Not true**.

Nothing is tracked and nothing leaves the device.

## The `play` section

The quiz and fact-or-fiction games come from a `play` section that each issue
carries alongside its `blocks`. It is never printed. The skeleton and every
paper's `PROMPT.md` ask for it, sized by the reader's age (ages 6–8: 3 questions
and 2 claims; 9–11: 4 and 3; 12–14: 5 and 3; 15+: 8 and 4):

```json
"play": {
  "quiz": [{"q": "Which ocean is running a fever?", "options": ["The Atlantic", "The Pacific", "The Indian"],
            "answer": 1, "why": "The top story says warm water is spreading across the Pacific.", "story": "lead"}],
  "fact_or_fiction": [{"claim": "Isaias was the first hurricane of the year.", "true": true,
                       "why": "The hurricane story says so.", "story": "us"}]
}
```

`python -m ygc check` makes sure each question has three different answers and
one right one, every claim says true or not, there is at least one of each, and
`story` names a story in the issue. Issues written before the section existed
get a note, not an error, and keep Word match. Papers from *Design your own*
don't ask the parent's chatbot for it.
