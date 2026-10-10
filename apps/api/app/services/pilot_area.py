import re
import unicodedata

from sqlalchemy import and_

from app.models.entities import POI

# Legacy District 1 boundary, simplified from a 2016 OSM-derived GeoJSON for
# relation 2587287. This names the historic pilot footprint, not a current
# district-level administrative unit. Coordinate order is (longitude, latitude).
# Source: https://gist.github.com/hoanganh25991/00e8f0162e41ac31ecd7
# Relation: https://www.openstreetmap.org/relation/2587287
# Data is ODbL; attribution: © OpenStreetMap contributors.
PILOT_DISTRICT_1_RING: tuple[tuple[float, float], ...] = (
    (106.6816512, 10.7654274), (106.6843154, 10.7682012),
    (106.6894226, 10.7736279), (106.6949544, 10.7795562),
    (106.6980875, 10.7828693), (106.6919813, 10.7878903),
    (106.6861523, 10.7925164), (106.6852419, 10.7942013),
    (106.6848289, 10.7959508), (106.6857222, 10.7969538),
    (106.6868809, 10.7952043), (106.6888549, 10.7955003),
    (106.6905607, 10.7957848), (106.6915377, 10.7955228),
    (106.6930831, 10.7948172), (106.6942381, 10.7949760),
    (106.6945413, 10.7937499), (106.6951421, 10.7933916),
    (106.6975106, 10.7936686), (106.6995624, 10.7935813),
    (106.7032960, 10.7928647), (106.7062142, 10.7918951),
    (106.7073086, 10.7899559), (106.7084029, 10.7881221),
    (106.7094457, 10.7874663), (106.7119563, 10.7877667),
    (106.7135957, 10.7871103), (106.7151836, 10.7852975),
    (106.7135420, 10.7841329), (106.7112300, 10.7825151),
    (106.7093793, 10.7791531), (106.7086819, 10.7769661),
    (106.7082205, 10.7731982), (106.7081991, 10.7714064),
    (106.7084384, 10.7695891), (106.7064395, 10.7690846),
    (106.7039322, 10.7681088), (106.7024737, 10.7670405),
    (106.7009309, 10.7650611), (106.6991821, 10.7640546),
    (106.6972244, 10.7620035), (106.6959468, 10.7603402),
    (106.6943171, 10.7592414), (106.6927620, 10.7583390),
    (106.6913135, 10.7573215), (106.6890914, 10.7553575),
    (106.6869967, 10.7532468), (106.6863102, 10.7548270),
    (106.6851488, 10.7565526), (106.6821368, 10.7641540),
)

PILOT_MIN_LONGITUDE = min(point[0] for point in PILOT_DISTRICT_1_RING)
PILOT_MAX_LONGITUDE = max(point[0] for point in PILOT_DISTRICT_1_RING)
PILOT_MIN_LATITUDE = min(point[1] for point in PILOT_DISTRICT_1_RING)
PILOT_MAX_LATITUDE = max(point[1] for point in PILOT_DISTRICT_1_RING)


def normalize_district(value: str | None) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFKD", value.strip().casefold())
    text = "".join(char for char in text if not unicodedata.combining(char)).replace("đ", "d")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def is_pilot_district(value: str | None) -> bool:
    """Legacy text matcher for non-spatial district queries only."""
    normalized = normalize_district(value)
    return bool(re.match(r"^(?:quan|district|q)\s*1(?:\D|$)", normalized))


def is_pilot_location(latitude: float, longitude: float) -> bool:
    """Return whether a WGS84 point is within the legacy District 1 pilot polygon."""
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return False
    if not (PILOT_MIN_LATITUDE <= latitude <= PILOT_MAX_LATITUDE and
            PILOT_MIN_LONGITUDE <= longitude <= PILOT_MAX_LONGITUDE):
        return False

    inside = False
    previous_longitude, previous_latitude = PILOT_DISTRICT_1_RING[-1]
    for current_longitude, current_latitude in PILOT_DISTRICT_1_RING:
        # Treat points exactly on the simplified boundary as in-scope.
        cross = ((longitude - previous_longitude) * (current_latitude - previous_latitude)
                 - (latitude - previous_latitude) * (current_longitude - previous_longitude))
        if abs(cross) < 1e-10 and (
            min(previous_longitude, current_longitude) - 1e-10 <= longitude <= max(previous_longitude, current_longitude) + 1e-10
            and min(previous_latitude, current_latitude) - 1e-10 <= latitude <= max(previous_latitude, current_latitude) + 1e-10
        ):
            return True
        if (current_latitude > latitude) != (previous_latitude > latitude):
            boundary_longitude = (
                (previous_longitude - current_longitude)
                * (latitude - current_latitude)
                / (previous_latitude - current_latitude)
                + current_longitude
            )
            if longitude < boundary_longitude:
                inside = not inside
        previous_longitude, previous_latitude = current_longitude, current_latitude
    return inside


def pilot_district_sql_filter():
    """Bounding-box prefilter; exact pilot inclusion is checked with the polygon."""
    return and_(
        POI.latitude.between(PILOT_MIN_LATITUDE, PILOT_MAX_LATITUDE),
        POI.longitude.between(PILOT_MIN_LONGITUDE, PILOT_MAX_LONGITUDE),
    )
