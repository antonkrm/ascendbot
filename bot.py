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
    handlers=[logging.FileHandler("bot.log", encoding="utf-8"), logging.StreamHandler()]
)
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
            [KeyboardButton(text="ℹ️ Помощь")]
        ],
        resize_keyboard=True
    )

async def send_safe_message(chat_id: int, text: str):
    """Отправка сообщения с контролем длины"""
    if len(text) <= 4096:
        await bot.send_message(chat_id, text, parse_mode="Markdown")
    else:
        parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
        for part in parts:
            await bot.send_message(chat_id, part, parse_mode="Markdown")
            await asyncio.sleep(0.3)

async def get_ai_response(prompt: str) -> str:
    """Получение интерпретации от ИИ"""
    try:
        completion = client.chat.completions.create(
            model=Config.MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=Config.MAX_TOKENS
        )
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
        parse_mode="Markdown"
    )

@dp.message(Command("natal"))
@dp.message(lambda message: message.text == "🌌 Натальная карта")
async def start_natal_chart(message: Message, state: FSMContext):
    await state.set_state(AstroStates.waiting_birth_date)
    await message.answer(
        "📅 Введите *дату рождения* в формате ДД.ММ.ГГГГ\n"
        "Пример: _15.05.1990_",
        parse_mode="Markdown"
    )

@dp.message(AstroStates.waiting_birth_date)
async def process_birth_date(message: Message, state: FSMContext):
    try:
        datetime.strptime(message.text, "%d.%m.%Y")
        await state.update_data(birth_date=message.text)
        await state.set_state(AstroStates.waiting_birth_time)
        await message.answer(
            "⏰ Введите *время рождения* в формате ЧЧ:ММ\n"
            "Пример: _14:30_",
            parse_mode="Markdown"
        )
    except ValueError:
        await message.answer(
            "❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ",
            parse_mode="Markdown"
        )

@dp.message(AstroStates.waiting_birth_time)
async def process_birth_time(message: Message, state: FSMContext):
    try:
        datetime.strptime(message.text, "%H:%M")
        await state.update_data(birth_time=message.text)
        await state.set_state(AstroStates.waiting_birth_place)
        await message.answer(
            "🌍 Введите *место рождения* (город, страна)\n"
            "Пример: _Москва, Россия_",
            parse_mode="Markdown"
        )
    except ValueError:
        await message.answer(
            "❌ Неверный формат времени. Используйте ЧЧ:ММ",
            parse_mode="Markdown"
        )

@dp.message(AstroStates.waiting_birth_place)
async def process_birth_place(message: Message, state: FSMContext):
    user_data = await state.get_data()
    place = message.text.strip()
    
    try:
        # 1. Расчет позиций планет
        positions = astro.calculate(
            user_data['birth_date'],
            user_data['birth_time'],
            place
        )
        
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
            f"{interpretation}"
        )
        
        await send_safe_message(message.chat.id, response)
        
    except ValueError as e:
        await message.answer(f"❌ Ошибка: {str(e)}")
    except Exception as e:
        logger.error(f"Natal chart error: {str(e)}")
        await message.answer("⚠️ Произошла ошибка при расчетах")
    finally:
        await state.clear()

if __name__ == '__main__':
    logger.info("Starting AstroBot...")
    dp.run_polling(bot)