"""IZC Who Will Win nine-cell codes. IDs are game enums, not roster indices."""

PLANT_CODES = dict(zip(
    (0, 2, 3, 4, 5, 6, 7, 8, 10, 12, 13, 14, 15, 17, 18, 20, 21,
     22, 23, 26, 28, 29, 30, 31, 32, 34, 36, 37, 39, 40, 42, 44, 46),
    ("peashooter", "cherry_bomb", "wallnut", "potato_mine", "snow_pea",
     "chomper", "repeater", "puff_shroom", "fume_shroom", "hypno_shroom",
     "scaredy_shroom", "ice_shroom", "doom_shroom", "squash", "threepeater",
     "jalapeno", "spikeweed", "torchwood", "tallnut", "cactus", "split_pea",
     "starfruit", "pumpkin", "magnet_shroom", "cabbage_pult", "kernelpult",
     "garlic", "umbrella_leaf", "melon_pult", "gatling_pea", "gloom_shroom",
     "winter_melon", "spikerock")))
ZOMBIE_CODES = dict(zip(
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 12, 15, 16, 17, 18, 19, 20, 21, 22,
     23, 24, 25, 26, 27, 28, 29, 30, 31, 32),
    ("normal", "flag", "conehead", "pole_vaulting", "buckethead", "newspaper",
     "screen_door", "football", "dancing", "zamboni", "jack_in_the_box",
     "balloon", "digger", "pogo", "yeti", "bungee", "ladder", "catapult",
     "gargantuar", "imp", "boss", "pea_head", "wallnut_head", "jalapeno_head",
     "gatling_head", "squash_head", "tallnut_head", "red_eye_gargantuar")))


def decode_formation(code, row=3):
    """Return placements, retaining token order for same-position tie breaks."""
    # Local import avoids a model -> importer -> model initialization cycle.
    from .model import ScenarioError
    if not isinstance(code, str):
        raise ScenarioError("formation_code: expected a nine-cell string")
    if type(row) is not int or not 1 <= row <= 5:
        raise ScenarioError("formation_row: expected an integer in 1..5")
    cells = code.strip().split("|")
    if len(cells) != 9:
        raise ScenarioError("formation_code: expected exactly nine cells separated by |")
    plants, zombies = [], []
    for col, cell in enumerate(cells, 1):
        cell = cell.strip()
        if cell == "_":
            continue
        main, shell, count = False, False, 0
        for raw in cell.split(","):
            token = raw.strip().upper()
            table = PLANT_CODES if token.startswith("P") else ZOMBIE_CODES
            if (len(token) < 2 or token[0] not in "PZ" or
                    not token[1:].isascii() or not token[1:].isdigit() or
                    str(int(token[1:])) != token[1:] or int(token[1:]) not in table):
                raise ScenarioError(f"formation_code cell {col}: unknown unit {raw!r}")
            kind = table[int(token[1:])]
            item = {"type": kind, "row": row, "col": col}
            if token[0] == "P":
                if kind == "pumpkin":
                    if shell:
                        raise ScenarioError(f"formation_code cell {col}: duplicate pumpkin")
                    shell = True
                else:
                    if main:
                        raise ScenarioError(f"formation_code cell {col}: multiple main plants")
                    main = True
                plants.append(item)
            else:
                count += 1
                if count > 3:
                    raise ScenarioError(f"formation_code cell {col}: more than three zombies")
                zombies.append(item)
    return {"plants": plants, "zombies": zombies}
