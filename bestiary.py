from utils import *

ATTACK_RE = re.compile(r'(?:<i>)?(?:\w+ ){1,4}Attack:(?:</i>)? ([+-]?\d+) to hit, .*?(?:<i>)?'
                       r'Hit:(?:</i>)? (?:(?:[+-]?\d+ \((.+?)\))|(?:([+-]?\d+))) (\w+) damage[., ]??'
                       r'(?:in melee, or [+-]?\d+ \((.+?)\) (\w+) damage at range[,.]?)?'
                       r'(?: or [+-]?\d+ \((.+?)\) (\w+) damage (?:\w+ ?)+[.,]?)?'
                       r'(?: ?plus [+-]?\d+ \((.+?)\) (\w+) damage)?', re.IGNORECASE)
JUST_DAMAGE_RE = re.compile(r'[+-]?\d+ \((.+?)\) (\w+) damage', re.IGNORECASE)
log = logging.getLogger("bestiary")


def get_bestiaries_from_web():
    try:
        with open('cache/monster.json') as f:
            monsters = json.load(f)
            log.info("Loaded monster data from cache")
    except FileNotFoundError:
        index = get_json('bestiary/index.json')
        monsters = []
        for src, file in index.items():
            if '3pp' in src:
                continue
            data = get_json(f"bestiary/{file}")
            monsters.extend(data['monster'])
            log.info(f"  Processed {file}: {len(data['monster'])} monsters")
        with open('cache/monster.json', 'w') as f:
            json.dump(monsters, f, indent=2)
    return monsters


def srdfilter(data):
    with open('srd/srd-monsters.txt') as f:
        srd = [s.strip().lower() for s in f.read().split('\n')]

    for monster in data:
        if monster['name'].lower() in srd:
            monster['srd'] = True
        else:
            monster['srd'] = False
    return data


def parse_ac(data):
    for monster in data:
        log.info(f"Parsing {monster['name']} AC")
        if isinstance(monster['ac'][0], int):
            monster['ac'] = {'ac': int(monster['ac'][0])}
        elif isinstance(monster['ac'][0], dict):
            monster['ac'] = {'ac': int(monster['ac'][0]['ac']),
                             'armortype': render(monster['ac'][0].get('from', []), join_char=', ')}
        else:
            log.warning(f"Unknown AC type: {monster['ac']}")
            raise Exception
    return data


def monster_render(data):
    for monster in data:
        log.info(f"Rendering {monster['name']}")
        for t in ('trait', 'action', 'reaction', 'legendary'):
            log.info(f"  Rendering {t}s")
            if t in monster:
                temp = []
                for entry in monster[t]:
                    text = render(entry['entries'])
                    temp.append({'name': entry.get('name', ''), 'text': text})
                monster[t] = temp

        if 'spellcasting' in monster:
            if 'trait' not in monster:
                monster['trait'] = []
            known_spells = []
            usual_dc = (0, 0)  # dc, number of spells using dc
            usual_sab = (0, 0)  # same thing
            caster_level = 1
            for cast_type in monster['spellcasting']:
                trait = {'name': cast_type['name'], 'text': render(cast_type['headerEntries'])}
                type_dc = re.search(r'\(spell save DC (\d+)', '\n'.join(cast_type['headerEntries']))
                type_sab = re.search(r'{@hit (\d+)}', '\n'.join(cast_type['headerEntries']))
                type_caster_level = re.search(r'(\d+)[stndrh]{2}-level', '\n'.join(cast_type['headerEntries']))
                type_spells = []
                if 'will' in cast_type:
                    type_spells.extend(extract_spell(s) for s in cast_type['will'])
                    spells = render(', '.join(cast_type['will']))
                    trait['text'] += f"\nAt will: {spells}"
                if 'daily' in cast_type:
                    for times_per_day, spells in cast_type['daily'].items():
                        each = ' each' if times_per_day.endswith('e') else ''
                        times_per_day = times_per_day.rstrip('e')
                        type_spells.extend(extract_spell(s) for s in spells)
                        spells = render(', '.join(spells))
                        trait['text'] += f"\n{times_per_day}/day{each}: {spells}"
                if 'spells' in cast_type:
                    for level, level_data in cast_type['spells'].items():
                        spells = level_data['spells']
                        level_text = get_spell_level(level)
                        slots = f"{level_data.get('slots', 'unknown')} slots" if level != '0' else "at will"
                        type_spells.extend(extract_spell(s) for s in spells)
                        spells = render(', '.join(spells))
                        trait['text'] += f"\n{level_text} ({slots}): {spells}"
                trait['text'] = render(trait['text'])
                monster['trait'].append(trait)
                known_spells.extend(type_spells)
                if type_dc and len(type_spells) > usual_dc[1]:
                    usual_dc = (int(type_dc.group(1)), len(type_spells))
                if type_sab and len(type_spells) > usual_sab[1]:
                    usual_sab = (int(type_sab.group(1)), len(type_spells))
                if type_caster_level:
                    caster_level = int(type_caster_level.group(1))
            dc = usual_dc[0]
            sab = usual_sab[0]
            monster['spellcasting'] = {'spells': known_spells, 'dc': dc, 'attackBonus': sab,
                                       'casterLevel': caster_level}  # overwrite old
            log.info(f"Lvl {caster_level}; DC: {dc}; SAB: {sab}; Spells: {known_spells}")
    return data


def extract_spell(text):
    return re.match(r'{@spell (.*)}', text).group(1)


def get_spell_level(level):
    if level == '0':
        return "Cantrips"
    if level == '1':
        return "1st level"
    if level == '2':
        return "2nd level"
    if level == '3':
        return "3rd level"
    return f"{level}th level"


def parse_attacks(data):
    for monster in data:
        attacks = []
        for t in ('trait', 'action', 'reaction', 'legendary'):
            if t in monster:
                for entry in monster[t]:
                    name = entry['name']
                    raw = entry['text']
                    raw_atks = list(ATTACK_RE.finditer(raw))
                    raw_damage = list(JUST_DAMAGE_RE.finditer(raw))

                    if raw_atks:
                        for atk in raw_atks:
                            if atk.group(7) and atk.group(8):  # versatile
                                damage = f"{atk.group(7)}[{atk.group(8)}]"
                                if atk.group(9) and atk.group(10):  # bonus damage
                                    damage += f"+{atk.group(9)}[{atk.group(10)}]"
                                attacks.append(
                                    {'name': f"2 Handed {name}", 'attackBonus': atk.group(1).lstrip('+'),
                                     'damage': damage,
                                     'details': raw})
                            if atk.group(5) and atk.group(6):  # ranged
                                damage = f"{atk.group(5)}[{atk.group(6)}]"
                                if atk.group(9) and atk.group(10):  # bonus damage
                                    damage += f"+{atk.group(9)}[{atk.group(10)}]"
                                attacks.append(
                                    {'name': f"Ranged {name}", 'attackBonus': atk.group(1).lstrip('+'),
                                     'damage': damage,
                                     'details': raw})
                            damage = f"{atk.group(2) or atk.group(3)}[{atk.group(4)}]"
                            if atk.group(9) and atk.group(10):  # bonus damage
                                damage += f"+{atk.group(9)}[{atk.group(10)}]"
                            attacks.append(
                                {'name': name, 'attackBonus': atk.group(1).lstrip('+'), 'damage': damage,
                                 'details': raw})
                    else:
                        index = 1
                        for dmg in raw_damage:
                            damage = f"{dmg.group(1)}[{dmg.group(2)}]"
                            if index > 1:
                                name = f"{name} {index}"
                            atk = {'name': name, 'attackBonus': None, 'damage': damage, 'details': raw}
                            attacks.append(atk)
                            index += 1
        monster['attacks'] = attacks
        log.debug(f"Parsed attacks for {monster['name']}: {attacks}")
    return data


def dump(data):
    with open('out/bestiary.json', 'w') as f:
        json.dump(data, f, indent=4)


def run():
    data = get_bestiaries_from_web()
    data = srdfilter(data)
    data = parse_ac(data)
    rendered = monster_render(data)
    rendered = recursive_tag(rendered)
    out = parse_attacks(rendered)
    dump(out)


if __name__ == '__main__':
    run()
