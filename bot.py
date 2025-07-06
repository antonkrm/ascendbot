import os
import json
import logging
from datetime import datetime
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from openai import OpenAI
from astro_engine import AstroCalculator

import asyncio

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler()
    ])
logger = logging.getLogger(__name__)

load_dotenv()


class Config:
    BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
    MODEL_NAME = "deepseek/deepseek-r1-0528:free"
    MAX_TOKENS = 2000


class AstroStates(StatesGroup):
    waiting_birth_date = State()
    waiting_birth_time = State()
    waiting_birth_place = State()


# Новый класс состояний для совместимости
class CompatibilityStates(StatesGroup):
    waiting_birth_date_1 = State()
    waiting_birth_time_1 = State()
    waiting_birth_place_1 = State()

    waiting_birth_date_2 = State()
    waiting_birth_time_2 = State()
    waiting_birth_place_2 = State()


bot = Bot(token=Config.BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
astro = AstroCalculator()

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=Config.OPENROUTER_API_KEY,
)


def get_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🌌 Натальная карта")],
            [KeyboardButton(text="❤️ Совместимость")
             ],  # Добавлена кнопка совместимости
            [KeyboardButton(text="ℹ️ Помощь")]
        ],
        resize_keyboard=True)


async def send_safe_message(chat_id: int, text: str):
    """Отправка сообщения с контролем длины"""
    if len(text) <= 4096:
        await bot.send_message(chat_id, text, parse_mode="Markdown")
    else:
        parts = [text[i:i + 4000] for i in range(0, len(text), 4000)]
        for part in parts:
            await bot.send_message(chat_id, part, parse_mode="Markdown")
            await asyncio.sleep(0.3)


async def get_ai_response(prompt: str) -> str:
    """Получение интерпретации от ИИ"""
    try:
        completion = client.chat.completions.create(
            model=Config.MODEL_NAME,
            messages=[{
                "role": "user",
                "content": prompt
            }],
            temperature=0.7,
            max_tokens=Config.MAX_TOKENS)
        return completion.choices[0].message.content
    except Exception as e:
        logger.error(f"AI error: {str(e)}")
        return "Не удалось получить интерпретацию"


@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "🔮 *AscendBot* - точные расчеты и персональные интерпретации вашей натальной карты\n"
        "Выберите действие:",
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown")


@dp.message(Command("natal"))
@dp.message(lambda message: message.text == "🌌 Натальная карта")
async def start_natal_chart(message: Message, state: FSMContext):
    await state.set_state(AstroStates.waiting_birth_date)
    await message.answer(
        "📅 Введите *дату рождения* в формате ДД.ММ.ГГГГ\n"
        "Пример: _15.05.1990_",
        parse_mode="Markdown")


@dp.message(AstroStates.waiting_birth_date)
async def process_birth_date(message: Message, state: FSMContext):
    try:
        datetime.strptime(message.text, "%d.%m.%Y")
        await state.update_data(birth_date=message.text)
        await state.set_state(AstroStates.waiting_birth_time)
        await message.answer(
            "⏰ Введите *время рождения* в формате ЧЧ:ММ\n"
            "Пример: _14:30_",
            parse_mode="Markdown")
    except ValueError:
        await message.answer("❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ",
                             parse_mode="Markdown")


@dp.message(AstroStates.waiting_birth_time)
async def process_birth_time(message: Message, state: FSMContext):
    try:
        datetime.strptime(message.text, "%H:%M")
        await state.update_data(birth_time=message.text)
        await state.set_state(AstroStates.waiting_birth_place)
        await message.answer(
            "🌍 Введите *место рождения* (город, страна)\n"
            "Пример: _Москва, Россия_",
            parse_mode="Markdown")
    except ValueError:
        await message.answer("❌ Неверный формат времени. Используйте ЧЧ:ММ",
                             parse_mode="Markdown")


@dp.message(AstroStates.waiting_birth_place)
async def process_birth_place(message: Message, state: FSMContext):
    user_data = await state.get_data()
    place = message.text.strip()

    try:
        # 1. Расчет позиций планет
        positions = astro.calculate(user_data['birth_date'],
                                    user_data['birth_time'], place)

        # 2. Формируем запрос для ИИ
        prompt = f"""
Рассчитана натальная карта:
- Дата: {user_data['birth_date']}
- Время: {user_data['birth_time']}
- Место: {place}

Позиции:
- Солнце: {positions['planets']['sun']['sign']} ({positions['planets']['sun']['degree']:.1f}°)
- Луна: {positions['planets']['moon']['sign']} ({positions['planets']['moon']['degree']:.1f}°)
- Асцендент: {positions['planets']['ascendant']['sign']} ({positions['planets']['ascendant']['degree']:.1f}°)

Дай краткую, лаконичную интерпретацию натальной карты с фокусом на:
- Основные черты (до 5 пунктов, кратко)
- Эмоциональные особенности (до 3–5 пунктов)
- 3 совета по развитию

Форматируй красиво, с эмодзи и подзаголовками. Избегай длинных абзацев. Не пиши 'На основе предоставленных данных...'
"""
        # 3. Получаем интерпретацию
        interpretation = await get_ai_response(prompt)

        # 4. Формируем ответ
        response = (
            f"🌠 *Натальная карта для {user_data['birth_date']}*\n"
            f"📍 Место: {place}\n\n"
            f"☀️ Солнце: {positions['planets']['sun']['sign']} ({positions['planets']['sun']['degree']:.1f}°)\n"
            f"🌙 Луна: {positions['planets']['moon']['sign']} ({positions['planets']['moon']['degree']:.1f}°)\n"
            f"↑ Асцендент: {positions['planets']['ascendant']['sign']} ({positions['planets']['ascendant']['degree']:.1f}°)\n\n"
            f"{interpretation}")

        await send_safe_message(message.chat.id, response)

    except ValueError as e:
        await message.answer(f"❌ Ошибка: {str(e)}")
    except Exception as e:
        logger.error(f"Natal chart error: {str(e)}")
        await message.answer("⚠️ Произошла ошибка при расчетах")
    finally:
        await state.clear()


# --- Новый функционал: Совместимость ---


@dp.message(Command("compatibility"))
@dp.message(lambda message: message.text == "❤️ Совместимость")
async def start_compatibility(message: Message, state: FSMContext):
    await state.set_state(CompatibilityStates.waiting_birth_date_1)
    await message.answer(
        "📅 Введите *дату рождения первого человека* в формате ДД.ММ.ГГГГ\n"
        "Пример: _15.05.1990_",
        parse_mode="Markdown")


@dp.message(CompatibilityStates.waiting_birth_date_1)
async def comp_birth_date_1(message: Message, state: FSMContext):
    try:
        datetime.strptime(message.text, "%d.%m.%Y")
        await state.update_data(birth_date_1=message.text)
        await state.set_state(CompatibilityStates.waiting_birth_time_1)
        await message.answer(
            "⏰ Введите *время рождения первого человека* в формате ЧЧ:ММ\n"
            "Пример: _14:30_",
            parse_mode="Markdown")
    except ValueError:
        await message.answer("❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ",
                             parse_mode="Markdown")


@dp.message(CompatibilityStates.waiting_birth_time_1)
async def comp_birth_time_1(message: Message, state: FSMContext):
    try:
        datetime.strptime(message.text, "%H:%M")
        await state.update_data(birth_time_1=message.text)
        await state.set_state(CompatibilityStates.waiting_birth_place_1)
        await message.answer(
            "🌍 Введите *место рождения первого человека* (город, страна)\n"
            "Пример: _Москва, Россия_",
            parse_mode="Markdown")
    except ValueError:
        await message.answer("❌ Неверный формат времени. Используйте ЧЧ:ММ",
                             parse_mode="Markdown")


@dp.message(CompatibilityStates.waiting_birth_place_1)
async def comp_birth_place_1(message: Message, state: FSMContext):
    try:
        # Проверка, что место не пустое
        place_1 = message.text.strip()
        if not place_1:
            await message.answer("❌ Место не может быть пустым")
            return
        await state.update_data(birth_place_1=place_1)
        await state.set_state(CompatibilityStates.waiting_birth_date_2)
        await message.answer(
            "📅 Введите *дату рождения второго человека* в формате ДД.ММ.ГГГГ\n"
            "Пример: _15.05.1990_",
            parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error comp_birth_place_1: {str(e)}")
        await message.answer("⚠️ Ошибка. Попробуйте еще раз.")


@dp.message(CompatibilityStates.waiting_birth_date_2)
async def comp_birth_date_2(message: Message, state: FSMContext):
    try:
        datetime.strptime(message.text, "%d.%m.%Y")
        await state.update_data(birth_date_2=message.text)
        await state.set_state(CompatibilityStates.waiting_birth_time_2)
        await message.answer(
            "⏰ Введите *время рождения второго человека* в формате ЧЧ:ММ\n"
            "Пример: _14:30_",
            parse_mode="Markdown")
    except ValueError:
        await message.answer("❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ",
                             parse_mode="Markdown")


@dp.message(CompatibilityStates.waiting_birth_time_2)
async def comp_birth_time_2(message: Message, state: FSMContext):
    try:
        datetime.strptime(message.text, "%H:%M")
        await state.update_data(birth_time_2=message.text)
        await state.set_state(CompatibilityStates.waiting_birth_place_2)
        await message.answer(
            "🌍 Введите *место рождения второго человека* (город, страна)\n"
            "Пример: _Москва, Россия_",
            parse_mode="Markdown")
    except ValueError:
        await message.answer("❌ Неверный формат времени. Используйте ЧЧ:ММ",
                             parse_mode="Markdown")


@dp.message(CompatibilityStates.waiting_birth_place_2)
async def comp_birth_place_2(message: Message, state: FSMContext):
    user_data = await state.get_data()
    place_2 = message.text.strip()

    try:
        if not place_2:
            await message.answer("❌ Место не может быть пустым")
            return

        await state.update_data(birth_place_2=place_2)
        user_data = await state.get_data()

        # Запускаем расчет совместимости
        pos1 = astro.calculate(user_data['birth_date_1'],
                               user_data['birth_time_1'],
                               user_data['birth_place_1'])
        pos2 = astro.calculate(user_data['birth_date_2'],
                               user_data['birth_time_2'],
                               user_data['birth_place_2'])

        # Формируем запрос для ИИ
        prompt = f"""
Даны две натальные карты для анализа совместимости:

1-й человек:
- Дата: {user_data['birth_date_1']}
- Время: {user_data['birth_time_1']}
- Место: {user_data['birth_place_1']}
- Солнце: {pos1['planets']['sun']['sign']} ({pos1['planets']['sun']['degree']:.1f}°)
- Луна: {pos1['planets']['moon']['sign']} ({pos1['planets']['moon']['degree']:.1f}°)
- Асцендент: {pos1['planets']['ascendant']['sign']} ({pos1['planets']['ascendant']['degree']:.1f}°)

2-й человек:
- Дата: {user_data['birth_date_2']}
- Время: {user_data['birth_time_2']}
- Место: {user_data['birth_place_2']}
- Солнце: {pos2['planets']['sun']['sign']} ({pos2['planets']['sun']['degree']:.1f}°)
- Луна: {pos2['planets']['moon']['sign']} ({pos2['planets']['moon']['degree']:.1f}°)
- Асцендент: {pos2['planets']['ascendant']['sign']} ({pos2['planets']['ascendant']['degree']:.1f}°)

Проанализируй совместимость этих двух людей, выдели сильные и слабые стороны их отношений,
эмоциональную и духовную совместимость, а также дай 3 практических совета для гармонии в паре.

Форматируй ответ с эмодзи и разделами, избегай воды и обобщений.
"""

        interpretation = await get_ai_response(prompt)

        response = (
            f"❤️ *Совместимость пары*\n\n"
            f"👤 1-й человек: {user_data['birth_date_1']}, {user_data['birth_place_1']}\n"
            f"☀️ Солнце: {pos1['planets']['sun']['sign']} ({pos1['planets']['sun']['degree']:.1f}°), "
            f"🌙 Луна: {pos1['planets']['moon']['sign']} ({pos1['planets']['moon']['degree']:.1f}°), "
            f"↑ Асцендент: {pos1['planets']['ascendant']['sign']} ({pos1['planets']['ascendant']['degree']:.1f}°)\n\n"
            f"👤 2-й человек: {user_data['birth_date_2']}, {user_data['birth_place_2']}\n"
            f"☀️ Солнце: {pos2['planets']['sun']['sign']} ({pos2['planets']['sun']['degree']:.1f}°), "
            f"🌙 Луна: {pos2['planets']['moon']['sign']} ({pos2['planets']['moon']['degree']:.1f}°), "
            f"↑ Асцендент: {pos2['planets']['ascendant']['sign']} ({pos2['planets']['ascendant']['degree']:.1f}°)\n\n"
            f"{interpretation}")

        await send_safe_message(message.chat.id, response)

    except ValueError as e:
        await message.answer(f"❌ Ошибка: {str(e)}")
    except Exception as e:
        logger.error(f"Compatibility error: {str(e)}")
        await message.answer("⚠️ Произошла ошибка при расчетах")
    finally:
        await state.clear()


@dp.message(lambda message: message.text == "ℹ️ Помощь")
async def help_message(message: Message):
    await message.answer(
        "Используйте кнопки:\n"
        "🌌 Натальная карта — получить вашу натальную карту с интерпретацией\n"
        "❤️ Совместимость — узнать астрологическую совместимость пары\n"
        "ℹ️ Помощь — показать это сообщение\n\n"
        "Вводите дату и время строго в формате, указанном в подсказках.")


if __name__ == "__main__":
    import asyncio

    async def main():
        try:
            await dp.start_polling(bot)
        finally:
            await bot.session.close()

    asyncio.run(main())
