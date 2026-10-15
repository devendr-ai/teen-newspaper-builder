"""Assemble tools/newspaper-builder.html from page.html + generator.js + presets.js (+ the owl logo).

    python tools/builder/build.py           # write the page
    python tools/builder/build.py --verify  # fail if the committed page is stale
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "newspaper-builder.html")


def assemble():
    read = lambda n: open(os.path.join(HERE, n), encoding="utf-8").read()
    presets = read("presets.js").replace('if (typeof module !== "undefined") module.exports = PRESETS;', "")
    owl = open(os.path.join(HERE, "..", "..", "assets", "owl.svg"), encoding="utf-8").read().strip()
    owl = owl.replace("<svg ", '<svg class="logo" aria-hidden="true" focusable="false" ', 1)
    return (read("page.html").replace("/*__GENERATOR__*/", read("generator.js")).replace("/*__PRESETS__*/", presets)
            .replace("<!--OWL-->", owl))


if __name__ == "__main__":
    html = assemble()
    if "--verify" in sys.argv:
        current = open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else ""
        if current != html:
            sys.exit("tools/newspaper-builder.html is stale: run python tools/builder/build.py")
        print("newspaper-builder.html up to date")
    else:
        open(OUT, "w", encoding="utf-8").write(html)
        print(f"wrote {OUT}")
