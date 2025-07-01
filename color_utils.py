# color_utils.py

import colorsys

def get_hsl_color_for_bar(bar_index: int, total_bars: int) -> str:
    """
    Calculates a color in HSL space and returns it as a hex string for tqdm.

    Args:
        bar_index: The zero-based index of the current progress bar.
        total_bars: The total number of progress bars that will be displayed.

    Returns:
        A hex color string (e.g., '#ff8080').
    """
    if total_bars == 0:
        return '#ffffff' # Default to white if no bars

    # Your logic is perfect: distribute the hue evenly.
    hue = (1.0 / total_bars) * bar_index
    saturation = 1.0
    lightness = 0.6  # A lightness of 0.6 is vibrant but readable on dark/light backgrounds

    # The colorsys module works with RGB values from 0 to 1.
    # It returns a tuple of (r, g, b).
    rgb_float = colorsys.hls_to_rgb(hue, lightness, saturation)

    # We need to convert the float values (0-1) to integer values (0-255).
    rgb_int = tuple(int(c * 255) for c in rgb_float)

    # Finally, format it as a hex string that tqdm understands.
    # The format string '{:02x}' pads with a leading zero if needed (e.g., 'f' becomes '0f').
    hex_color = f"#{rgb_int[0]:02x}{rgb_int[1]:02x}{rgb_int[2]:02x}"
    
    return hex_color