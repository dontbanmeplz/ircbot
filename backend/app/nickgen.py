"""Human-looking IRC nickname generator and client fingerprint randomizer.

Generates nicknames that blend in with real IRC users and realistic
CTCP VERSION replies so the bot doesn't stick out.
"""

import random

# --- Nickname generation ---
# Patterns people actually use on IRC: name + interest, adjective + noun,
# name + numbers, hobby + suffix, etc.

_FIRST_NAMES = [
    "alex", "sam", "jamie", "chris", "jordan", "taylor", "casey", "morgan",
    "riley", "drew", "quinn", "blake", "avery", "emma", "jake", "mike",
    "sarah", "dana", "lee", "max", "nora", "finn", "luna", "kai", "remy",
    "ash", "eli", "jess", "rob", "dan", "tom", "kat", "nina", "owen",
    "ivy", "cole", "zara", "seth", "mia", "ben", "tess", "luke", "aria",
]

_ADJECTIVES = [
    "quiet", "lazy", "dusty", "sleepy", "chill", "late", "lost", "odd",
    "pale", "cold", "dark", "slow", "wild", "old", "new", "dry", "raw",
]

_NOUNS = [
    "shelf", "page", "ink", "owl", "fox", "cat", "wolf", "rain",
    "book", "lamp", "dusk", "moon", "frog", "moth", "pine", "crow",
    "leaf", "salt", "mist", "haze", "fern", "reed", "wren", "lark",
]

_INTERESTS = [
    "reads", "lit", "books", "pages", "txt", "pdf", "words", "prose",
    "fiction", "paper", "novel", "chap",
]

_SUFFIXES = [
    "42", "99", "77", "13", "88", "23", "07", "66", "31", "404",
    "ix", "x", "o", "ie", "ey", "er", "ly", "ish",
    "_", "__",
]


def generate_nick() -> str:
    """Generate a random human-looking IRC nickname.
    
    Picks from several patterns real users tend to use:
      - name + interest:  emma_lit, jake_reads
      - name + numbers:   sam42, chris07
      - adjective + noun: quiet_owl, dusty_shelf
      - name + suffix:    lunaish, remy_
      - noun + numbers:   moth99, page23
    
    Nicks are kept to 9-16 chars to look natural.
    """
    pattern = random.choice([
        "name_interest",
        "name_interest",  # weighted more common
        "name_num",
        "name_num",
        "adj_noun",
        "adj_noun",
        "name_suffix",
        "noun_num",
        "plain_name",
    ])

    if pattern == "name_interest":
        name = random.choice(_FIRST_NAMES)
        interest = random.choice(_INTERESTS)
        sep = random.choice(["_", "-", ""])
        num = random.choice(["", "", "", str(random.randint(1, 99))])
        nick = f"{name}{sep}{interest}{num}"

    elif pattern == "name_num":
        name = random.choice(_FIRST_NAMES)
        num = str(random.randint(1, 999))
        sep = random.choice(["_", "", ""])
        nick = f"{name}{sep}{num}"

    elif pattern == "adj_noun":
        adj = random.choice(_ADJECTIVES)
        noun = random.choice(_NOUNS)
        sep = random.choice(["_", "-", ""])
        num = random.choice(["", "", str(random.randint(1, 99))])
        nick = f"{adj}{sep}{noun}{num}"

    elif pattern == "name_suffix":
        name = random.choice(_FIRST_NAMES)
        suffix = random.choice(_SUFFIXES)
        nick = f"{name}{suffix}"

    elif pattern == "noun_num":
        noun = random.choice(_NOUNS)
        num = str(random.randint(1, 999))
        nick = f"{noun}{num}"

    else:  # plain_name
        name = random.choice(_FIRST_NAMES)
        nick = name

    # IRC nicks can't start with a digit or hyphen
    if nick[0].isdigit() or nick[0] == "-":
        nick = "_" + nick

    # Clamp length to something normal
    nick = nick[:16]

    return nick


# --- CTCP VERSION replies ---
# Real version strings from popular IRC clients. Rotate these so the
# bot doesn't always fingerprint the same way.

_VERSION_STRINGS = [
    "mIRC v7.75 Khaled Mardam-Bey",
    "mIRC v7.73",
    "mIRC v7.72 Khaled Mardam-Bey",
    "HexChat 2.16.2 [x64] / Windows 10 (10.0)",
    "HexChat 2.16.1 [x64] / Windows 11 (10.0)",
    "HexChat 2.16.0 / Linux 6.1.0",
    "irssi v1.4.5 - running on Linux x86_64",
    "irssi v1.4.4 - running on Linux x86_64",
    "KVIrc 5.2.0 Quasar - Build 2024-01-15 - Windows",
    "KVIrc 5.0.0 Aria - Build 2022-08-10",
    "LimeChat for macOS - v2.42",
    "Textual 5.7.0 - macOS 14.0",
    "Textual 5.6.0 - macOS 13.5",
    "WeeChat 4.1.2",
    "WeeChat 4.0.5",
    "AndroIRC 6.1.3 - Android 13",
    "Revolution IRC 0.6.1 - Android",
]


def random_version_string() -> str:
    """Return a random realistic CTCP VERSION reply."""
    return random.choice(_VERSION_STRINGS)
