# The owl

`owl.svg` is News Pebbles' logo: a little owl reading the paper, in the River stone colours
(slate-blue owl `#5A8394`, ears `#47707F`, coral headline `#E2584D`). It is the one drawing
everything else comes from:

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

The name is drawn as text beside the owl (`brand.wordmark()`): "News" in ink, "Pebbles" in
coral, and three small stones underneath (slate `#8E9AA0`, sand `#D9C7A3`, moss `#9DB48A`). Those
three stones and Read & Play's pebble tower are the only pebble shapes; everything else keeps
ordinary shapes.
