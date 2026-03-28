import h3 as h3lib


def gps_to_h3(lat: float, lon: float, resolution: int = 7) -> str:
    """
    Convert GPS coordinates to an H3 hexagon cell index.

    Resolution 7 = roughly 5 km² per cell — neighborhood level.
    The returned string looks like: "872b8e254ffffff"

    Usage:
        h3_index = gps_to_h3(51.1801, 71.4460)  # Astana, Kazakhstan
    """
    return h3lib.latlng_to_cell(lat, lon, resolution)


def get_neighbors(h3_index: str, ring: int = 1) -> list[str]:
    """
    Return all H3 cells within `ring` hops of the given cell.

    ring=1 returns the center cell + 6 neighbors = 7 cells total.
    ring=2 returns 19 cells, ring=3 returns 37 cells, etc.

    Used in analytics to show demand in surrounding neighborhoods.
    """
    return list(h3lib.k_ring(h3_index, ring))


def h3_to_center(h3_index: str) -> tuple[float, float]:
    """
    Return the (latitude, longitude) of the center of an H3 cell.

    Used in analytics to convert h3_index back to map coordinates
    so the frontend can place a pin on the map.
    """
    return h3lib.cell_to_latlng(h3_index)