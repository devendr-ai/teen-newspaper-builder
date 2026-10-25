"""Refresh assets/fonts/web from Google Fonts (run by hand; the files are committed).

    python tools/brand/fonts.py

Downloads the exact families, weights and unicode ranges the site uses, as WOFF2, and writes
assets/fonts/web/fonts.css pointing at the local files, so pages never contact Google.
Both fonts are under the SIL Open Font License (assets/fonts/OFL-*.txt), which allows this.
"""
import os
import re
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "..", "assets", "fonts", "web")
CSS = ("https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible:ital,wght@0,400;0,700;1,400"
       "&family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,700;12..96,800&display=swap")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
HEADER = """/* News Pebbles' fonts, served from this site (no outside requests).
   Atkinson Hyperlegible and Bricolage Grotesque, SIL Open Font License (see ../OFL-*.txt).
   The same files and unicode ranges Google Fonts serves; refresh with tools/brand/fonts.py. */
"""


def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60).read()


def main():
    css = get(CSS).decode()
    names, blocks = {}, []
    for subset, block in re.findall(r"/\* ([a-z-]+) \*/\s*(@font-face \{.*?\})", css, re.S):
        family = re.search(r"font-family: '([^']+)'", block).group(1)
        italic = re.search(r"font-style: (\w+)", block).group(1) == "italic"
        weight = re.search(r"font-weight: (\d+)", block).group(1)
        url = re.search(r"url\((https://[^)]+)\)", block).group(1)
        if url not in names:
            base = family.replace(" ", "") + ("-Italic" if italic else "")
            names[url] = f"{base}-{subset}.woff2" if "Bricolage" in family else f"{base}-{weight}-{subset}.woff2"
            open(os.path.join(OUT, names[url]), "wb").write(get(url))
        blocks.append(f"/* {subset} */\n" + block.replace(url, names[url]))
    open(os.path.join(OUT, "fonts.css"), "w", encoding="utf-8").write(HEADER + "\n".join(blocks) + "\n")
    print(f"{len(names)} font files in {os.path.normpath(OUT)}")


if __name__ == "__main__":
    main()
