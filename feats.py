import json
import logging

from utils import get_data

log = logging.getLogger("feats")


def get_latest_feats():
    return get_data("feats.json")['feat']


def srdfilter(data):
    for feat in data:
        if feat['name'].lower() == 'grappler':
            feat['srd'] = True
        else:
            feat['srd'] = False
    return data


def dump(data):
    with open('out/feats.json', 'w') as f:
        json.dump(data, f, indent=4)


def run():
    data = get_latest_feats()
    data = srdfilter(data)
    dump(data)


if __name__ == '__main__':
    run()
