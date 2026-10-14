# The world map

`countries.topo.json` is the country map behind Read & Play's "Where in the world?" maps.

It comes from [Natural Earth](https://www.naturalearthdata.com/) (public domain), version 5.1. We use the
**India point-of-view** edition of the 1:10m countries, `ne_10m_admin_0_countries_ind`, so India's borders
appear as on India's official maps. The site is for families in India, and Indian law expects this.

It was made smaller with [mapshaper](https://github.com/mbloch/mapshaper) 0.6.102. The command drops
Antarctica, keeps four fields, and simplifies the shapes to 2% while keeping every country:

```sh
echo UTF-8 > ne_10m_admin_0_countries_ind.cpg
mapshaper ne_10m_admin_0_countries_ind.shp \
  -filter 'CONTINENT != "Antarctica"' \
  -filter-fields NAME,ISO_A2,LABEL_X,LABEL_Y \
  -simplify 2% keep-shapes -filter-slivers min-area=200km2 \
  -o countries.topo.json format=topojson quantization=20000
```

`ygc/world.py` reads it, draws it in the Equal Earth projection, and writes `play/world.js` for the website.
