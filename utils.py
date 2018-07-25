import json
import logging
import re
import sys

import requests

DATA_SRC = "https://5etools.com/data/"

log_formatter = logging.Formatter('%(levelname)s:%(name)s: %(message)s')
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(log_formatter)
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(handler)
log = logging.getLogger(__name__)


def get_json(path):
    log.info(f"Getting {path}...")
    return requests.get(DATA_SRC + path).json()


def get_data(path):
    try:
        with open(f'cache/{path}') as f:
            dat = json.load(f)
            log.info(f"Loaded {path} from cache")
    except FileNotFoundError:
        dat = get_json(path)
        with open(f'cache/{path}', 'w') as f:
            json.dump(dat, f, indent=2)
    return dat


def nth_repl(s, sub, repl, nth):
    find = s.find(sub)
    # if find is not p1 we have found at least one match for the substring
    i = find != -1
    # loop util we find the nth or we find no match
    while find != -1 and i != nth:
        # find + 1 means we start at the last match start index + 1
        find = s.find(sub, find + 1)
        i += 1
    # if i  is equal to nth we found nth matches so replace
    if i == nth:
        return s[:find] + repl + s[find + len(sub):]
    return s


ABILITY_MAP = {'str': 'Strength', 'dex': 'Dexterity', 'con': 'Constitution',
               'int': 'Intelligence', 'wis': 'Wisdom', 'cha': 'Charisma'}
ATTACK_TYPES = {"M": "Melee", "R": "Ranged", "W": "Weapon", "S": "Spell"}


def render(text, md_breaks=False, join_char='\n'):
    """Parses a list or string from astranauta data.
    :returns str - The final text."""
    if not isinstance(text, list):
        return parse_data_formatting(str(text))

    out = []
    join_str = f'{join_char}' if not md_breaks else f'  {join_char}'

    for entry in text:
        if not isinstance(entry, dict):
            out.append(str(entry))
        elif isinstance(entry, dict):
            if not 'type' in entry and 'title' in entry:
                out.append(f"**{entry['title']}**: {render(entry['text'])}")
            elif not 'type' in entry and 'istable' in entry:  # only for races
                temp = f"**{entry['caption']}**\n" if 'caption' in entry else ''
                temp += ' - '.join(f"**{cl}**" for cl in entry['thead']) + '\n'
                for row in entry['tbody']:
                    temp += ' - '.join(f"{col}" for col in row) + '\n'
                out.append(temp.strip())
            elif entry['type'] == 'entries':
                out.append((f"**{entry['name']}**: " if 'name' in entry else '') + render(
                    entry['entries']))  # oh gods here we goooooooo
            elif entry['type'] == 'options':
                pass  # parsed separately in classfeat
            elif entry['type'] == 'list':
                out.append('\n'.join(f"- {t}" for t in entry['items']))
            elif entry['type'] == 'table':
                temp = f"**{entry['caption']}**\n" if 'caption' in entry else ''
                temp += ' - '.join(f"**{cl}**" for cl in entry['colLabels']) + '\n'
                for row in entry['rows']:
                    temp += ' - '.join(f"{col}" for col in row) + '\n'
                out.append(temp.strip())
            elif entry['type'] == 'invocation':
                pass  # this is only found in options
            elif entry['type'] == 'abilityAttackMod':
                out.append(f"`{entry['name']} Attack Bonus = "
                           f"{' or '.join(ABILITY_MAP.get(a) for a in entry['attributes'])}"
                           f" modifier + Proficiency Bonus`")
            elif entry['type'] == 'abilityDc':
                out.append(f"`{entry['name']} Save DC = 8 + "
                           f"{' or '.join(ABILITY_MAP.get(a) for a in entry['attributes'])}"
                           f" modifier + Proficiency Bonus`")
            elif entry['type'] == 'bonus':
                out.append("{:+}".format(entry['value']))
            elif entry['type'] == 'dice':
                out.append(f"{entry['number']}d{entry['faces']}")
            elif entry['type'] == 'bonusSpeed':
                out.append(f"{entry['value']} feet")
            elif entry['type'] == 'actions':
                out.append((f"**{entry['name']}**: " if 'name' in entry else '') + render(entry['entries']))
            elif entry['type'] == 'attack':
                out.append(f"{' '.join(ATTACK_TYPES.get(t) for t in entry['attackType'])} Attack: "
                           f"{render(entry['attackEntries'])} Hit: {render(entry['hitEntries'])}")
            else:
                log.warning(f"Missing astranauta entry type parse: {entry}")

        else:
            log.warning(f"Unknown astranauta entry: {entry}")

    return parse_data_formatting(join_str.join(out))


FORMATTING = {'bold': '**', 'italic': '*', 'b': '**', 'i': '*'}
PARSING = {'creature': lambda e: e.split('|')[-1], 'item': lambda e: e.split('|')[0], 'hit': lambda e: f"{int(e):+}"}


def parse_data_formatting(text):
    """Parses a {@format } string."""
    exp = re.compile(r'{@(\w+) (.+?)}')

    def sub(match):
        if match.group(1) in PARSING:
            f = PARSING.get(match.group(1), lambda e: e)
            return f(match.group(2))
        else:
            f = FORMATTING.get(match.group(1), '')
            if not match.group(1) in FORMATTING:
                log.warning(f"Unknown tag: {match.group(1)}")
            return f"{f}{match.group(2)}{f}"

    while exp.search(text):
        text = exp.sub(sub, text)
    return text
