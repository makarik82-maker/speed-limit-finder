from typing import Optional

from models import Road, SpeedResult


def parse_speed(value: Optional[str]) -> Optional[int]:
    """
    Пытается извлечь числовое значение скорости из OSM.

    Примеры:
        "60"       -> 60
        "60 km/h"  -> 60
        "90"       -> 90
        None       -> None

    Если значение не удалось распознать,
    возвращается None.
    """

    if not value:
        return None

    value = str(value).strip().lower()

    # Специальные значения OSM
    if value in {
        "none",
        "signals",
        "variable",
        "national",
        "walk",
        "unposted",
    }:
        return None

    # Иногда значение может выглядеть как:
    # "60 km/h"
    # "90 mph"
    parts = value.replace(",", ".").split()

    try:
        speed = float(parts[0])

        # Если скорость указана в mph,
        # переводим в км/ч.
        if len(parts) > 1 and parts[1] in ("mph", "mi/h"):
            speed *= 1.60934

        return round(speed)

    except (ValueError, TypeError):
        return None


def determine_speed(
    road: Road,
    inside_settlement: Optional[bool],
) -> SpeedResult:
    """
    Определяет разрешённую скорость.

    Приоритет:

    1. maxspeed
    2. maxspeed:forward
    3. maxspeed:backward
    4. расчёт по общим правилам РФ

    Важно:
    расчётное значение является предположением.
    Оно не учитывает дорожные знаки, временные ограничения,
    ограничения для отдельных категорий транспорта и т.п.
    """

    # ---------------------------------------------------------
    # 1. Явно указан maxspeed
    # ---------------------------------------------------------

    speed = parse_speed(road.maxspeed)

    if speed is not None:
        return SpeedResult(
            speed_kmh=speed,
            source="OSM maxspeed",
            is_estimated=False,
            explanation=(
                "Скорость непосредственно указана "
                "в данных OpenStreetMap."
            ),
        )

    # ---------------------------------------------------------
    # 2. Если общего maxspeed нет, смотрим направления
    # ---------------------------------------------------------

    speed_forward = parse_speed(road.maxspeed_forward)

    if speed_forward is not None:
        return SpeedResult(
            speed_kmh=speed_forward,
            source="OSM maxspeed:forward",
            is_estimated=False,
            explanation=(
                "Общее значение maxspeed отсутствует, "
                "но в OSM указано ограничение "
                "для направления forward."
            ),
        )

    speed_backward = parse_speed(road.maxspeed_backward)

    if speed_backward is not None:
        return SpeedResult(
            speed_kmh=speed_backward,
            source="OSM maxspeed:backward",
            is_estimated=False,
            explanation=(
                "Общее значение maxspeed отсутствует, "
                "но в OSM указано ограничение "
                "для направления backward."
            ),
        )

    # ---------------------------------------------------------
    # 3. Специальные типы дорог
    # ---------------------------------------------------------

    road_type = (road.road_type or "").lower()

    # Жилая зона.
    #
    # В OSM highway=living_street обычно соответствует
    # дороге/проезду в жилой зоне.
    #
    # По ПДД РФ в жилой зоне действует ограничение 20 км/ч.
    if road_type == "living_street":
        return SpeedResult(
            speed_kmh=20,
            source="ПДД РФ — предполагаемое значение",
            is_estimated=True,
            explanation=(
                "Для highway=living_street принято "
                "предположение о жилой зоне. "
                "По ПДД РФ скорость в жилой зоне — 20 км/ч. "
                "Необходимо учитывать реальные дорожные знаки."
            ),
        )

    # ---------------------------------------------------------
    # 4. Автомагистраль
    # ---------------------------------------------------------

    if road_type == "motorway":
        return SpeedResult(
            speed_kmh=110,
            source="ПДД РФ — предполагаемое значение",
            is_estimated=True,
            explanation=(
                "Для автомагистрали maxspeed отсутствует "
                "в OSM. Использовано общее ограничение "
                "для легкового автомобиля на автомагистрали "
                "вне населённого пункта — 110 км/ч."
            ),
        )

    # ---------------------------------------------------------
    # 5. Населённый пункт
    # ---------------------------------------------------------

    if inside_settlement is True:
        return SpeedResult(
            speed_kmh=60,
            source="ПДД РФ — предполагаемое значение",
            is_estimated=True,
            explanation=(
                "maxspeed отсутствует в OSM. "
                "Точка находится в населённом пункте. "
                "Принято общее ограничение 60 км/ч. "
                "Фактическое ограничение может отличаться "
                "из-за дорожных знаков."
            ),
        )

    # ---------------------------------------------------------
    # 6. Дорога вне населённого пункта
    # ---------------------------------------------------------

    if inside_settlement is False:
        return SpeedResult(
            speed_kmh=90,
            source="ПДД РФ — предполагаемое значение",
            is_estimated=True,
            explanation=(
                "maxspeed отсутствует в OSM. "
                "Точка находится вне населённого пункта. "
                "Принято общее ограничение 90 км/ч "
                "для легкового автомобиля. "
                "Фактическое ограничение может отличаться."
            ),
        )

    # ---------------------------------------------------------
    # 7. Не удалось определить населённый пункт
    # ---------------------------------------------------------

    return SpeedResult(
        speed_kmh=None,
        source="Не определено",
        is_estimated=True,
        explanation=(
            "В OSM отсутствует maxspeed, а определить "
            "нахождение точки в населённом пункте "
            "не удалось. Безопаснее не предполагать "
            "конкретное ограничение скорости."
        ),
    )