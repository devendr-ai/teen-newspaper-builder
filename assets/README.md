# The owl

`owl.svg` is The Kids' Newsstand's logo: a little owl reading the paper. It is the one
drawing everything else comes from:

- the website's header and browser-tab icon (`python -m ygc site` copies it);
- the builder page's header (`tools/builder/build.py` puts it in);
- Read & Play's home-screen icons, `owl-icon-180/192/512.png`, and `owl-32.png`;
- the printed masthead of papers with a QR code (`ygc/brand.py` draws the same SVG in the PDF).

After changing `owl.svg`, redraw the PNGs and rebuild the builder page:

```sh
NODE_PATH=$(npm root -g) node tools/brand/make_icons.js
python tools/builder/build.py
```

`ygc/brand.py` understands only what the owl uses: paths with absolute M, L, H, V, C and Z,
circles, and rounded rectangles. Keep new shapes to those.
