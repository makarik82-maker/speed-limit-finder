import math
import time
from typing import List, Optional, Tuple

import requests

from models import Road


OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]


def haversine_distance(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    """
    Расстояние между двумя GPS-точками в метрах.
    """

    earth_radius = 6371000.0

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)

    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad)
        * math.cos(lat2_rad)
        * math.sin(delta_lon / 2) ** 2
    )

    c = 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a),
    )

    return earth_radius * c


def build_overpass_query(
    latitude: float,
    longitude: float,
    radius: int = 100,
) -> str:
    """
    Формирует Overpass QL-запрос.

    Ищем highway-way в радиусе radius метров.
    """

    return f"""
[out:json][timeout:25];

way["highway"](around:{radius},{latitude},{longitude});

out body geom;
"""


def request_overpass(
    query: str,
) -> dict:
    """
    Отправляет запрос в Overpass.

    Используется несколько серверов с резервированием.
    """

    last_error = None

    for url in OVERPASS_URLS:

        try:
            response = requests.post(
                url,
                data=query.encode("utf-8"),
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "User-Agent": (
                        "GitHub-Speed-Limit-Finder/1.0 "
                        "(OpenStreetMap research tool)"
                    ),
                },
                timeout=40,
            )

            response.raise_for_status()

            return response.json()

        except Exception as exc:
            last_error = exc

            print(
                f"Ошибка запроса к Overpass {url}: {exc}"
            )

            time.sleep(2)

    raise RuntimeError(
        "Не удалось получить данные от Overpass API. "
        f"Последняя ошибка: {last_error}"
    )


def calculate_way_distance(
    latitude: float,
    longitude: float,
    geometry: List[dict],
) -> float:
    """
    Вычисляет минимальное расстояние от GPS-точки
    до вершин геометрии OSM way.

    Для версии 1.0 используется расстояние до ближайшей
    точки геометрии.

    Это достаточно для поиска ближайшей дороги,
    но в дальнейшем можно сделать более точное
    расстояние до сегмента линии.
    """

    if not geometry:
        return float("inf")

    minimum = float("inf")

    for point in geometry:

        point_lat = point.get("lat")
        point_lon = point.get("lon")

        if point_lat is None or point_lon is None:
            continue

        distance = haversine_distance(
            latitude,
            longitude,
            point_lat,
            point_lon,
        )

        if distance < minimum:
            minimum = distance

    return minimum


def find_nearest_roads(
    latitude: float,
    longitude: float,
    radius: int = 100,
) -> List[Road]:
    """
    Находит дороги рядом с координатами.

    Возвращает список дорог,
    отсортированный по расстоянию.
    """

    query = build_overpass_query(
        latitude,
        longitude,
        radius,
    )

    data = request_overpass(query)

    roads = []

    for element in data.get("elements", []):

        if element.get("type") != "way":
            continue

        tags = element.get("tags", {})
        geometry = element.get("geometry", [])

        road_type = tags.get("highway")

        if not road_type:
            continue

        distance = calculate_way_distance(
            latitude,
            longitude,
            geometry,
        )

        if math.isinf(distance):
            continue

        road = Road(
            osm_id=int(element["id"]),

            road_type=road_type,

            name=tags.get("name"),

            maxspeed=tags.get("maxspeed"),

            latitude=latitude,

            longitude=longitude,

            distance_meters=distance,

            maxspeed_forward=tags.get(
                "maxspeed:forward"
            ),

            maxspeed_backward=tags.get(
                "maxspeed:backward"
            ),

            surface=tags.get("surface"),

            ref=tags.get("ref"),

            lanes=tags.get("lanes"),
        )

        roads.append(road)

    roads.sort(
        key=lambda road: road.distance_meters
    )

    return roads


def find_nearest_road(
    latitude: float,
    longitude: float,
) -> Optional[Road]:
    """
    Ищет ближайшую дорогу.

    Сначала радиус 50 м.
    Если ничего не найдено — 100 м.
    Затем — 250 м.
    """

    radiuses = [50, 100, 250]

    for radius in radiuses:

        print(
            f"Поиск дорог в радиусе {radius} м..."
        )

        roads = find_nearest_roads(
            latitude,
            longitude,
            radius,
        )

        if roads:
            return roads[0]

    return None


def reverse_geocode(
    latitude: float,
    longitude: float,
) -> Tuple[Optional[bool], Optional[str]]:
    """
    Определяет, находится ли точка в населённом пункте.

    Используется Nominatim OpenStreetMap.

    Возвращает:

        (True,  название)
        (False, название)
        (None, None)

    """

    url = "https://nominatim.openstreetmap.org/reverse"

    params = {
        "lat": latitude,
        "lon": longitude,
        "format": "jsonv2",
        "zoom": 18,
        "addressdetails": 1,
        "accept-language": "ru",
    }

    headers = {
        "User-Agent": (
            "GitHub-Speed-Limit-Finder/1.0 "
            "(OpenStreetMap research tool)"
        )
    }

    try:

        response = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=20,
        )

        response.raise_for_status()

        data = response.json()

        address = data.get("address", {})

        settlement = (
            address.get("city")
            or address.get("town")
            or address.get("village")
            or address.get("municipality")
            or address.get("hamlet")
        )

        if settlement:
            return True, settlement

        return False, None

    except Exception as exc:

        print(
            f"Не удалось определить населённый пункт: {exc}"
        )

        return None, None