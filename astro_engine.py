import ephem
import pytz
import math
from timezonefinder import TimezoneFinder
from datetime import datetime
from geopy.geocoders import Nominatim
from typing import Dict, Any

class AstroCalculator:
    def __init__(self):
        self.tf = TimezoneFinder()
        self.geolocator = Nominatim(user_agent="astro_bot_v2")
    
    def get_coords(self, place: str) -> tuple:
        """Получаем координаты места через геокодер"""
        try:
            location = self.geolocator.geocode(place)
            if not location:
                raise ValueError("Место не найдено")
            return (location.latitude, location.longitude)
        except Exception as e:
            raise ValueError(f"Ошибка геокодинга: {str(e)}")
    
    def calculate_ascendant(self, observer: ephem.Observer) -> Dict[str, Any]:
        """Расчет асцендента (восходящего знака)"""
        try:
            # Рассчитываем асцендент через эклиптику
            observer.pressure = 0  # Убираем рефракцию
            observer.date = observer.date  # Обновляем время
            
            # Получаем эклиптическую долготу восточного горизонта
            ra, dec = observer.radec_of(0, 0)
            ecl = ephem.Ecliptic(ra, dec)
            
            # Преобразуем в зодиакальный знак
            sign_num = int(ecl.lon / math.pi * 6) % 12
            signs = [
                "Овен", "Телец", "Близнецы", "Рак", 
                "Лев", "Дева", "Весы", "Скорпион",
                "Стрелец", "Козерог", "Водолей", "Рыбы"
            ]
            
            return {
                "sign": signs[sign_num],
                "degree": (ecl.lon / math.pi * 180) % 30,
                "position": f"{ecl.lon:.4f}"
            }
        except Exception as e:
            raise ValueError(f"Ошибка расчета асцендента: {str(e)}")
    
    def calculate(self, date_str: str, time_str: str, place: str) -> Dict[str, Any]:
        """
        Основная функция расчета натальной карты
        Возвращает словарь с позициями планет
        """
        try:
            # Парсинг даты и времени
            dt = datetime.strptime(f"{date_str} {time_str}", "%d.%m.%Y %H:%M")
            lat, lon = self.get_coords(place)
            
            # Настройка наблюдателя
            observer = ephem.Observer()
            observer.lat = str(lat)
            observer.lon = str(lon)
            observer.date = dt
            
            # Расчет основных точек
            sun = ephem.Sun(observer)
            moon = ephem.Moon(observer)
            ascendant = self.calculate_ascendant(observer)
            
            return {
                "planets": {
                    "sun": {
                        "sign": ephem.constellation(sun)[1],
                        "position": str(sun),
                        "degree": self._get_degree(sun)
                    },
                    "moon": {
                        "sign": ephem.constellation(moon)[1],
                        "position": str(moon),
                        "degree": self._get_degree(moon)
                    },
                    "ascendant": ascendant
                },
                "metadata": {
                    "date": date_str,
                    "time": time_str,
                    "place": place,
                    "coordinates": f"{lat:.4f}, {lon:.4f}",
                    "timezone": self.tf.timezone_at(lat=lat, lng=lon),
                    "calculation_time": datetime.now().isoformat()
                }
            }
        except Exception as e:
            raise ValueError(f"Ошибка расчета: {str(e)}")
    
    def _get_degree(self, body: ephem.Body) -> float: # type: ignore
        """Вычисляем градус положения планеты"""
        return float(body.ra) * 180 / ephem.pi % 30