"""ygc — a configurable, print-ready newspaper engine.

An *edition* (editions/<id>/edition.yaml) describes the paper: reader, purpose,
desks, cadence and page plan. An *issue* (editions/<id>/issues/YYYY/YYYY-MM-DD.json)
holds one issue's content, keyed by the edition's block ids.
"""
__version__ = "4.0.0"
