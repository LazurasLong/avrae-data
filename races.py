import copy
import json
import logging

from utils import get_json

SRD = ['Dragonborn', 'Half-Elf', 'Half-Orc', 'Elf (High)', 'Dwarf (Hill)', 'Human', 'Human (Variant)',
       'Halfling (Lightfoot)', 'Gnome (Rock)', 'Tiefling']
SOURCE_HIERARCHY = ['MTF', 'VGM', 'PHB', 'DMG', 'UAWGtE', 'UA', 'nil']
EXPLICIT_SOURCES = ['UAEberron', 'DMG']

log = logging.getLogger("races")


def get_races_from_web():
    try:
        with open('cache/races.json') as f:
            races = json.load(f)
            log.info("Loaded race data from cache")
    except FileNotFoundError:
        races = get_json('races.json')['race']
        with open('cache/races.json', 'w') as f:
            json.dump(races, f, indent=2)
    return races


def split_subraces(races):
    out = []
    for race in races:
        log.info(f"Processing race {race['name']}")
        if 'subraces' not in race:
            out.append(race)
        else:
            subraces = race['subraces']
            del race['subraces']
            for subrace in subraces:
                log.info(f"Processing subrace {subrace.get('name')}")
                new = copy.deepcopy(race)
                if 'name' in subrace:
                    new['name'] = f"{race['name']} ({subrace['name']})"
                if 'entries' in subrace:
                    new['entries'].extend(subrace['entries'])
                if 'ability' in subrace:
                    if 'ability' in new:
                        new['ability'].update(subrace['ability'])
                    else:
                        new['ability'] = subrace['ability']
                if 'speed' in subrace:
                    new['speed'] = subrace['speed']
                if 'source' in subrace:
                    new['source'] = subrace['source']
                out.append(new)
    return out


def explicit_sources(data):
    for r in data:
        if r['source'] in EXPLICIT_SOURCES:
            new_name = f"{r['name']} ({r['source']})"
            log.info(f"Renaming {r['name']} to {new_name} (explicit override)")
            r['name'] = new_name
    return data


def fix_dupes(data):
    for race in data:
        if len([r for r in data if r['name'] == race['name']]) > 1:
            log.warning(f"Found duplicate: {race['name']}")
            hierarchied = sorted([r for r in data if r['name'] == race['name']],
                                 key=lambda r: SOURCE_HIERARCHY.index(
                                     next((s for s in SOURCE_HIERARCHY if s in r['source']), 'nil')))
            for r in hierarchied[1:]:
                new_name = f"{r['name']} ({r['source']})"
                log.info(f"Renaming {r['name']} to {new_name}")
                r['name'] = new_name
    return data


def srdfilter(data):
    for race in data:
        if race['name'] in SRD:
            race['srd'] = True
        else:
            race['srd'] = False
    return data


def dump(data):
    with open('out/races.json', 'w') as f:
        json.dump(data, f, indent=4)


def run():
    data = get_races_from_web()
    data = split_subraces(data)
    data = explicit_sources(data)
    data = fix_dupes(data)
    data = srdfilter(data)
    dump(data)


if __name__ == '__main__':
    run()
