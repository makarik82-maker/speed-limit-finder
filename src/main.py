import argparse
import json
import os
import sys
from datetime import datetime, timezone

from osm import (
    find_nearest_road,
    reverse_geocode,
)

from road import determine_speed


def validate_coordinate(
    value: float,
    minimum: float,
    maximum: float,
    name: str,
) -> None:
    """
    Проверяет диапазон GPS-координаты.
    """

    if not minimum <= value <= maximum:
        raise ValueError(
            f"{name} имеет недопустимое значение: {value}. "
            f"Допустимый диапазон: "
            f"{minimum} ... {maximum}"
        )


def format_speed(
    speed: int | None,
) -> str:
    """
    Форматирует скорость для вывода.
    """

    if speed is None:
        return "НЕ ОПРЕДЕЛЕНО"

    return f"{speed} км/ч"


def main() -> int:

    parser = argparse.ArgumentParser(
        description=(
            "Определение ближайшей дороги и "
            "разрешённой скорости по GPS."
        )
    )

    parser.add_argument(
        "--latitude",
        type=float,
        required=True,
        help="Широта",
    )

    parser.add_argument(
        "--longitude",
        type=float,
        required=True,
        help="Долгота",
    )

    parser.add_argument(
        "--output",
        default="result.json",
        help="Файл для сохранения результата",
    )

    args = parser.parse_args()

    latitude = args.latitude
    longitude = args.longitude

    # ---------------------------------------------------------
    # Проверка координат
    # ---------------------------------------------------------

    try:

        validate_coordinate(
            latitude,
            -90,
            90,
            "Широта",
        )

        validate_coordinate(
            longitude,
            -180,
            180,
            "Долгота",
        )

    except ValueError as exc:

        print(f"❌ Ошибка: {exc}")

        return 1

    print()
    print("=" * 60)
    print("ПОИСК ОГРАНИЧЕНИЯ СКОРОСТИ")
    print("=" * 60)

    print()
    print(
        f"GPS: {latitude:.6f}, {longitude:.6f}"
    )

    # ---------------------------------------------------------
    # Поиск ближайшей дороги
    # ---------------------------------------------------------

    print()
    print("Ищем ближайшую дорогу...")

    try:

        road = find_nearest_road(
            latitude,
            longitude,
        )

    except Exception as exc:

        print()
        print(
            "❌ Ошибка при обращении к OpenStreetMap:"
        )

        print(exc)

        return 1

    if road is None:

        print()
        print(
            "❌ Дорога в радиусе 250 метров не найдена."
        )

        return 2

    # ---------------------------------------------------------
    # Определяем населённый пункт
    # ---------------------------------------------------------

    print()
    print("Определяем населённый пункт...")

    inside_settlement, settlement_name = reverse_geocode(
        latitude,
        longitude,
    )

    # ---------------------------------------------------------
    # Определяем скорость
    # ---------------------------------------------------------

    speed_result = determine_speed(
        road,
        inside_settlement,
    )

    # ---------------------------------------------------------
    # Вывод
    # ---------------------------------------------------------

    print()
    print("=" * 60)
    print("РЕЗУЛЬТАТ")
    print("=" * 60)

    print()

    print(
        f"📍 Координаты: "
        f"{latitude:.6f}, {longitude:.6f}"
    )

    print(
        f"🛣 Дорога: "
        f"{road.name or 'Название не указано'}"
    )

    if road.ref:

        print(
            f"🔢 Номер дороги: {road.ref}"
        )

    print(
        f"🏷 Тип OSM: {road.road_type}"
    )

    print(
        f"🆔 OSM way ID: {road.osm_id}"
    )

    print(
        f"📏 Расстояние до дороги: "
        f"{road.distance_meters:.1f} м"
    )

    if settlement_name:

        print(
            f"🏙 Населённый пункт: "
            f"{settlement_name}"
        )

    elif inside_settlement is False:

        print(
            "🌲 Населённый пункт: "
            "не определён / вероятно вне населённого пункта"
        )

    else:

        print(
            "🏙 Населённый пункт: "
            "не удалось определить"
        )

    print()

    if road.maxspeed:

        print(
            f"🗺 OSM maxspeed: "
            f"{road.maxspeed}"
        )

    else:

        print(
            "🗺 OSM maxspeed: отсутствует"
        )

    if road.maxspeed_forward:

        print(
            f"➡️ maxspeed:forward: "
            f"{road.maxspeed_forward}"
        )

    if road.maxspeed_backward:

        print(
            f"⬅️ maxspeed:backward: "
            f"{road.maxspeed_backward}"
        )

    print()

    print(
        f"🚗 РАЗРЕШЁННАЯ СКОРОСТЬ: "
        f"{format_speed(speed_result.speed_kmh)}"
    )

    print(
        f"📚 Источник: "
        f"{speed_result.source}"
    )

    if speed_result.is_estimated:

        print()
        print(
            "⚠️ ВНИМАНИЕ: значение ПРЕДПОЛАГАЕМОЕ."
        )

        print(
            "Оно рассчитано по общим правилам РФ, "
            "так как конкретный maxspeed не найден "
            "в OSM."
        )

    print()
    print(
        f"ℹ️ {speed_result.explanation}"
    )

    print()
    print("=" * 60)

    # ---------------------------------------------------------
    # Сохраняем результат
    # ---------------------------------------------------------

    result = {
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),

        "coordinates": {
            "latitude": latitude,
            "longitude": longitude,
        },

        "road": {
            "osm_id": road.osm_id,
            "name": road.name,
            "ref": road.ref,
            "highway": road.road_type,
            "distance_meters": round(
                road.distance_meters,
                2,
            ),
            "surface": road.surface,
            "lanes": road.lanes,
        },

        "osm_speed": {
            "maxspeed": road.maxspeed,
            "maxspeed_forward": (
                road.maxspeed_forward
            ),
            "maxspeed_backward": (
                road.maxspeed_backward
            ),
        },

        "location": {
            "inside_settlement": (
                inside_settlement
            ),
            "settlement": settlement_name,
        },

        "speed": {
            "value_kmh": (
                speed_result.speed_kmh
            ),
            "source": speed_result.source,
            "estimated": (
                speed_result.is_estimated
            ),
            "explanation": (
                speed_result.explanation
            ),
        },
    }

    output_directory = os.path.dirname(
        args.output
    )

    if output_directory:

        os.makedirs(
            output_directory,
            exist_ok=True,
        )

    with open(
        args.output,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            result,
            file,
            ensure_ascii=False,
            indent=2,
        )

    print()
    print(
        f"💾 Результат сохранён: "
        f"{args.output}"
    )

    return 0


if __name__ == "__main__":

    sys.exit(main())