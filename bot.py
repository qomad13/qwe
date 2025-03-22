import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import locale
import httpx
from datetime import datetime, timedelta
import random
import json

TOKEN = ""
API_URL = "http://127.0.0.1:8000"
CURRENCIES = {
    "USD": ("$", "Доллар США"),
    "EUR": ("€", "Евро"),
    "UAH": ("₴", "Гривна"),
    "PLN": ("zł", "Злотый"),
    "GBP": ("£", "Фунт стерлингов")
}

locale.setlocale(locale.LC_ALL, 'ru_RU.UTF-8')

bot = Bot(token=TOKEN)
dp = Dispatcher()

user_data = {}
history_data = {}

def format_number(value):
    """Форматирует числа через пробел, например 1 234,56"""
    return f"{value:,.2f}".replace(",", " ").replace(".", ",")

def format_currency(amount, currency_code):
    symbol, name = CURRENCIES[currency_code]
    return f"{format_number(amount)} {symbol} ({name})"

# Основное меню
def main_menu_keyboard():
    buttons = [
        [InlineKeyboardButton(text="Конвертация", callback_data="convert")],
        [InlineKeyboardButton(text="История курса", callback_data="history")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def currency_keyboard(callback_prefix):
    buttons = [
        [InlineKeyboardButton(text=f"{cur}", callback_data=f"{callback_prefix}_{cur}") ] 
        for cur in CURRENCIES.keys()
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

@dp.message(Command("start"))
async def start_command(message: types.Message):
    await message.answer("Выберите действие:", reply_markup=main_menu_keyboard())

@dp.callback_query(lambda c: c.data in ["convert", "history"])
async def handle_action(callback: types.CallbackQuery):
    if callback.data == "convert":
        await callback.message.answer("Выберите валюту для конвертации:", reply_markup=currency_keyboard("convert"))
    elif callback.data == "history":
        await callback.message.answer("Выберите базовую валюту для истории курса:", reply_markup=currency_keyboard("history_base"))
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("convert_"))
async def select_currency_convert(callback: types.CallbackQuery):
    currency = callback.data.split("_")[1]
    user_data[callback.from_user.id] = currency
    await callback.message.answer(f"Вы выбрали {CURRENCIES[currency][1]}. Введите сумму для конвертации:")
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("history_base_"))
async def select_base_currency_history(callback: types.CallbackQuery):
    base_currency = callback.data.split("_")[2]
    history_data[callback.from_user.id] = {"base_currency": base_currency}
    await callback.message.answer("Введите количество дней для истории (например, 7):")
    await callback.answer()

@dp.message(lambda message: message.text.isdigit())
async def handle_numeric_input(message: types.Message):
    user_id = message.from_user.id

    if user_id in user_data:
        amount = float(message.text)
        from_currency = user_data.pop(user_id)

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(f"{API_URL}/convert/", params={"amount": amount, "from_currency": from_currency})
                data = response.json()
            except:
                data = {"converted": {cur: amount * random.uniform(0.5, 1.5) for cur in CURRENCIES.keys() if cur != from_currency}}

        converted = data.get("converted", {})
        result = f"Конвертация {format_number(amount)} {CURRENCIES[from_currency][0]} ({CURRENCIES[from_currency][1]}):\n\n" + "\n".join(
            f"{format_number(value)} {CURRENCIES[currency][0]} ({CURRENCIES[currency][1]})" for currency, value in converted.items()
        )

        await message.answer(result)
        await message.answer("Выберите следующее действие:", reply_markup=main_menu_keyboard())

    elif user_id in history_data:
        days = int(message.text)
        base_currency = history_data.pop(user_id)["base_currency"]

        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        end_date = datetime.now().strftime("%Y-%m-%d")

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{API_URL}/history/", params={
                    "from_currency": base_currency,
                    "start_date": start_date,
                    "end_date": end_date
                })
                data = response.json()
            except:
                data = {"history": {  
                    (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d"): 
                    {cur: round(random.uniform(0.8, 1.2), 2) for cur in CURRENCIES.keys() if cur != base_currency}
                    for i in range(days)
                }}

        history = data.get("history", {})

        result = f"История курса {CURRENCIES[base_currency][1]} за {days} дней:\n\n"
        for date, rates in sorted(history.items(), reverse=True):
            rates_str = ", ".join(f"{format_number(rate)} {CURRENCIES[cur][0]} ({CURRENCIES[cur][1]})" for cur, rate in rates.items())
            result += f"{date}: {rates_str}\n"

        await message.answer(result)
        await message.answer("Выберите следующее действие:", reply_markup=main_menu_keyboard())

async def main():
    dp.startup.register(lambda: print("Бот запущен"))
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
