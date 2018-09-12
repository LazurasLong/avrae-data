import json
import logging
import re
import sys

import requests

DATA_SRC = "https://5etools.com/data/"
LOGLEVEL = logging.INFO if not "debug" in sys.argv else logging.DEBUG

log_formatter = logging.Formatter('%(levelname)s:%(name)s: %(message)s')
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(log_formatter)
logger = logging.getLogger()
logger.setLevel(LOGLEVEL)
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
    if isinstance(text, dict):
        text = [text]
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
                temp += ' - '.join(f"**{parse_data_formatting(cl)}**" for cl in entry['thead']) + '\n'
                for row in entry['tbody']:
                    temp += ' - '.join(f"{parse_data_formatting(col)}" for col in row) + '\n'
                out.append(temp.strip())
            elif entry['type'] == 'entries':
                out.append((f"**{entry['name']}**: " if 'name' in entry else '') + render(
                    entry['entries']))  # oh gods here we goooooooo
            elif entry['type'] == 'options':
                pass  # parsed separately in classfeat
            elif entry['type'] == 'list':
                out.append('\n'.join(f"- {render(t)}" for t in entry['items']))
            elif entry['type'] == 'table':
                temp = f"**{entry['caption']}**\n" if 'caption' in entry else ''
                temp += ' - '.join(f"**{parse_data_formatting(cl)}**" for cl in entry['colLabels']) + '\n'
                for row in entry['rows']:
                    temp += ' - '.join(f"{render(col)}" for col in row) + '\n'
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
            elif entry['type'] == 'item':
                out.append(f"*{entry['name']}* {render(entry['entry'])}")
            elif entry['type'] == 'cell':
                out.append(render(entry['entry']))
            else:
                log.warning(f"Missing astranauta entry type parse: {entry}")

        else:
            log.warning(f"Unknown astranauta entry: {entry}")

    return parse_data_formatting(join_str.join(out))


def SRC_FORMAT(e):
    return e.split('|')[0] if len(e.split('|')) < 3 else e.split('|')[-1]


ATK_TYPES = {'mw': "Melee Weapon", 'rw': "Ranged Weapon", 'mw,rw': "Melee or Ranged Weapon",
             'ms': "Melee Spell", 'rs': "Ranged Spell", 'ms,rs': "Melee or Ranged Spell"}
FORMATTING = {'bold': '**', 'italic': '*', 'b': '**', 'i': '*'}
PARSING = {'hit': lambda e: f"{int(e):+}",
           'filter': lambda e: e.split('|')[0],
           'link': lambda e: f"[{e.split('|')[0]}]({e.split('|')[1]})",
           'adventure': lambda e: e.split('|')[0],
           'recharge': lambda e: f"(Recharge {e}-6)" if e else "(Recharge 6)",
           'chance': lambda e: e.split('|')[1],
           'atk': lambda e: f"{ATK_TYPES.get(e, 'Unknown')} Attack:"}
IGNORED = ['dice', 'condition', 'skill', 'action', 'creature', 'item', 'spell', 'damage']


def parse_data_formatting(text):
    """Parses a {@format } string."""
    exp = re.compile(r'{@(\w+)(?: ([^{}]+?))?}')

    def sub(match):
        log.debug(f"Rendering {match.group(0)}...")
        if match.group(1) in IGNORED:
            out = SRC_FORMAT(match.group(2))
        elif match.group(1) in PARSING:
            f = PARSING.get(match.group(1), lambda e: e)
            out = f(match.group(2))
        else:
            f = FORMATTING.get(match.group(1), '')
            if not match.group(1) in FORMATTING:
                log.warning(f"Unknown tag: {match.group(0)}")
            out = f"{f}{match.group(2)}{f}"
        log.debug(f"Replaced with {out}")
        return out

    while exp.search(text):
        text = exp.sub(sub, text)
    return text


def recursive_tag(value):
    """
    Recursively renders all tags.
    :param value: The object to render tags from.
    :return: The object, with all tags rendered.
    """
    if isinstance(value, str):
        return render(value)
    if isinstance(value, list):
        return [recursive_tag(i) for i in value]
    if isinstance(value, dict):
        for k, v in value.items():
            value[k] = recursive_tag(v)
    return value
