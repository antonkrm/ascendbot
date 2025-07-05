import swisseph as swe
import pytz
from datetime import datetime
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class AstroCalculator:
    def __init__(self):
        self.geolocator = Nominatim(user_agent="ascend_bot_geocoder")
        self.tz_finder = TimezoneFinder()
        self.signs = [
            "Овен", "Телец", "Близнецы", "Рак", "Лев", "Дева",
            "Весы", "Скорпион", "Стрелец", "Козерог", "Водолей", "Рыбы"
        ]
        swe.set_ephe_path('.')  # путь к эфемеридам (по умолчанию — текущая папка)

    def get_coordinates_and_timezone(self, place: str) -> tuple:
        try:
            location = self.geolocator.geocode(place)
            if not location:
                raise ValueError("Место не найдено")

            lat, lon = location.latitude, location.longitude
            timezone_str = self.tz_finder.timezone_at(lat=lat, lng=lon)

            if not timezone_str:
                raise ValueError("Часовой пояс не найден")

            logger.info(f"Место: {place}, Координаты: {lat}, {lon}, Таймзона: {timezone_str}")
            return lat, lon, timezone_str
        except Exception as e:
            logger.error(f"Ошибка геокодинга/таймзоны: {e}")
            raise

    def get_julian_day(self, dt: datetime) -> float:
        return swe.julday(dt.year, dt.month, dt.day, dt.hour + dt.minute / 60)

    def get_planet_info(self, jd: float, planet_id: int) -> Dict[str, Any]:
        lon = swe.calc_ut(jd, planet_id)[0][0]
        sign = self.signs[int(lon // 30)]
        degree = lon % 30
        return {"sign": sign, "degree": degree}

    def get_ascendant(self, jd: float, lat: float, lon: float) -> Dict[str, Any]:
        try:
            houses, ascmc = swe.houses(jd, lat, lon, b'P')  # P — Placidus
            asc = ascmc[0]
            sign = self.signs[int(asc // 30)]
            degree = asc % 30
            return {"sign": sign, "degree": degree}
        except Exception as e:
            logger.error(f"Ошибка расчета асцендента: {e}")
            raise

    def calculate(self, date_str: str, time_str: str, place: str) -> Dict[str, Any]:
        try:
            # Преобразуем дату и время
            dt_naive = datetime.strptime(f"{date_str} {time_str}", "%d.%m.%Y %H:%M")
            lat, lon, tz_str = self.get_coordinates_and_timezone(place)

            tz = pytz.timezone(tz_str)
            dt_local = tz.localize(dt_naive)
            dt_utc = dt_local.astimezone(pytz.utc)

            logger.info(f"Местное время: {dt_local}, UTC: {dt_utc}")

            # Юлианская дата в UTC
            jd = self.get_julian_day(dt_utc)

            sun = self.get_planet_info(jd, swe.SUN)
            moon = self.get_planet_info(jd, swe.MOON)
            ascendant = self.get_ascendant(jd, lat, lon)

            return {
                "planets": {
                    "sun": sun,
                    "moon": moon,
                    "ascendant": ascendant
                },
                "metadata": {
                    "place": place,
                    "date_local": dt_local.isoformat(),
                    "timezone": tz_str,
                    "coordinates": f"{lat:.4f}, {lon:.4f}"
                }
            }
        except Exception as e:
            logger.exception("Ошибка общего расчета")
            raise ValueError(f"Ошибка общего расчета: {str(e)}")
