from dataclasses import dataclass
from typing import Optional


@dataclass
class Road:
    """
    Информация о найденном участке дороги.
    """

    osm_id: int
    road_type: str
    name: Optional[str]
    maxspeed: Optional[str]

    latitude: float
    longitude: float

    distance_meters: float

    maxspeed_forward: Optional[str] = None
    maxspeed_backward: Optional[str] = None

    surface: Optional[str] = None
    ref: Optional[str] = None

    lanes: Optional[str] = None


@dataclass
class SpeedResult:
    """
    Итоговый результат определения разрешённой скорости.
    """

    speed_kmh: Optional[int]

    source: str

    is_estimated: bool

    explanation: str