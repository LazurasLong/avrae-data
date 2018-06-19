import json
import logging

from utils import get_data

log = logging.getLogger("items")


def get_latest_items():
    return get_data("items.json")['item'] + get_data("basicitems.json")['basicitem'] + get_data("magicvariants.json")[
        'variant']


def moneyfilter(data):
    return [i for i in data if not i.get('type') == "$"]


def srdfilter(data):
    OVERRIDES = ('+1', '+2', '+3', 'giant strength', 'ioun stone', 'horn of valhalla', 'vorpal', 'of sharpness',
                 'of answering', 'instrument of the bard', 'nine lives', 'frost brand', 'carpet of flying', 'vicious',
                 'of wounding', 'of life stealing', 'of protection', 'adamantine', 'of wondrous power', 'luck blade')
    TYPES = ('W', 'P', 'ST', 'RD', 'RG', 'WD')
    with open('srd/srd-items.txt') as f:
        srd = [s.strip().lower() for s in f.read().split('\n')]

    for item in data:
        if item['name'].lower() in srd or any(i in item['name'].lower() for i in OVERRIDES) or not any(
                i in item.get('type', '').split(',') for i in TYPES):
            item['srd'] = True
        else:
            item['srd'] = False
    return data


def variant_inheritance(data):
    for item in data:
        if item.get('type') == 'GV':
            if 'entries' in item:
                oldentries = item['entries'].copy()
                item.update(item['inherits'])
                item['entries'] = oldentries
            else:
                item.update(item['inherits'])
    return data


def dump(data):
    with open('out/items.json', 'w') as f:
        json.dump(data, f, indent=4)


def run():
    data = get_latest_items()
    data = moneyfilter(data)
    data = srdfilter(data)
    data = variant_inheritance(data)
    dump(data)  # TODO: DMG object parse


if __name__ == '__main__':
    run()
