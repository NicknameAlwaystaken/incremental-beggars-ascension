import math

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
        return f"{value_str}{prefix}"
    else:
        return value_str
