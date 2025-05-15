from __future__ import annotations
import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import discord
    from modules.player_classes import Player

ACTIVITIES_PER_PAGE = 4

TASKS_PER_PAGE = 5

LOCATIONS_PER_PAGE = 5

UPGRADES_PER_PAGE = 4


def set_embed_footer(embed: discord.Embed, player: Player):
    if player.current_location:
        location_png = player.current_location.icon_png
        location_name = player.current_location.name

        embed.set_footer(text=location_name,icon_url=f"https://raw.githubusercontent.com/NicknameAlwaystaken/incremental-beggars-ascension/refs/heads/main/images/location/{location_png}.png")


def set_embed_thumbnail(embed: discord.Embed, player: Player):
    if player.current_activity:
        activity_name = player.current_activity.name.lower()
        # turn file name into snake case
        file_name = activity_name.replace(" ", "_")
        embed.set_thumbnail(
            url=f"https://raw.githubusercontent.com/NicknameAlwaystaken/incremental-beggars-ascension/refs/heads/main/images/activity/{file_name}.png"
        )


def format_time(time_in_seconds: float):
    seconds = int(time_in_seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60

    time_string = []

    if hours:
        time_string.append(f'{hours:.0f}h')

    if minutes:
        time_string.append(f'{minutes}m')

    if seconds > 0 or len(time_string) == 0:
        time_string.append(f'{seconds}s')

    return " ".join(time_string)


def format_number(number: float, sig_figs=3):
    prefixes = {
        0: '',
        3: 'K',
        6: 'M',
        9: 'B',
        12: 'T',
    }
    if number == 0:
        return "0"

    if number < 1:
        return f"{number:.2f}"

    # Determine exponent and adjusted value
    exponent = int(math.floor(math.log10(abs(number)) / 3) * 3)
    value = number / (10 ** exponent)

    # Format the value with the specified significant figures
    format_string = "{:." + str(sig_figs - 1) + "f}"
    value_str = format_string.format(value).rstrip('0').rstrip('.')

    # Get the large number name
    prefix = prefixes.get(exponent, f"e{exponent}")

    if prefix:
        return f"{value_str}**{prefix}**"
    else:
        return value_str
