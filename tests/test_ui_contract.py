from html.parser import HTMLParser
from pathlib import Path

from pet_engine import SUPPORTED_DEMO_EVENTS

ROOT = Path(__file__).resolve().parents[1]


class Collector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.demo_types = set()

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if 'id' in attributes:
            assert attributes['id'] not in self.ids, f"Duplicate HTML ID: {attributes['id']}"
            self.ids.add(attributes['id'])
        if 'data-demo' in attributes:
            assert tag == 'button'
            self.demo_types.add(attributes['data-demo'])


def test_frontend_controls_match_demo_api():
    parser = Collector()
    parser.feed((ROOT / 'static' / 'index.html').read_text())
    assert parser.demo_types == SUPPORTED_DEMO_EVENTS.keys()
    for value in ('pet-stage','pet-level','pet-mood','health-value','health-bar',
                  'energy-value','energy-bar','stress-value','stress-bar',
                  'xp-label','xp-bar','cpu-value','ram-value','cpu-status',
                  'ram-status','cpu-line','ram-line','feed-items',
                  'event-count','alerts-count','terminal-output',
                  'tail-indicator','tail-command','toast','connection-status','local-date'):
        assert value in parser.ids, f"Missing dashboard element #{value}"
