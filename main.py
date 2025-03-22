from fastapi import FastAPI, Query, HTTPException
import httpx
import time
import asyncio
import json

app = FastAPI()

# Конфигурация API
EXTERNAL_API_URL = "https://v6.exchangerate-api.com/v6/*********/latest"
HISTORICAL_API_URL = "https://v6.exchangerate-api.com/v6/*********/history"
CACHED_RATES = {}
CACHE_EXPIRATION = 3600  # 1 час
CURRENCIES = ["USD", "EUR", "UAH", "PLN", "GBP"]  # Ваши 5 валют

# Фоновая задача для обновления курсов валют
async def update_exchange_rates():
    while True:
        async with httpx.AsyncClient() as client:
            for base_currency in CURRENCIES:
                response = await client.get(f"{EXTERNAL_API_URL}/{base_currency}")
                if response.status_code == 200:
                    data = response.json()
                    rates = data.get("conversion_rates", {})
                    # Оставляем только нужные валюты
                    filtered_rates = {currency: rates[currency] for currency in CURRENCIES if currency in rates}
                    CACHED_RATES[base_currency] = {
                        "rates": filtered_rates,
                        "timestamp": time.time()
                    }
        await asyncio.sleep(CACHE_EXPIRATION)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(update_exchange_rates())

@app.get("/convert/")
async def convert(amount: float = Query(...), from_currency: str = Query(...)):
    """
    Эндпоинт для конвертации валют.
    """
    current_time = time.time()

    if from_currency in CACHED_RATES and current_time - CACHED_RATES[from_currency]["timestamp"] < CACHE_EXPIRATION:
        rates = CACHED_RATES[from_currency]["rates"]
    else:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{EXTERNAL_API_URL}/{from_currency}")
            if response.status_code != 200:
                raise HTTPException(status_code=500, detail="Ошибка при запросе к внешнему API")
            data = response.json()
            rates = data.get("conversion_rates", {})
            # Оставляем только нужные валюты
            rates = {currency: rate for currency, rate in rates.items() if currency in CURRENCIES}
            CACHED_RATES[from_currency] = {
                "rates": rates,
                "timestamp": current_time
            }

    converted = {currency: amount * rate for currency, rate in rates.items() if currency in CURRENCIES}

    return {
        "amount": amount,
        "from": from_currency,
        "converted": converted
    }

@app.get("/history/")
async def get_history(from_currency: str = Query(...), start_date: str = Query(...), end_date: str = Query(...)):
    """
    Эндпоинт для получения истории курсов валют.
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{HISTORICAL_API_URL}/{from_currency}", params={
            "start_date": start_date,
            "end_date": end_date
        })
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="Ошибка при запросе к внешнему API")
        data = response.json()
        rates = data.get("rates", {})

        if not rates:
            raise HTTPException(status_code=404, detail="Исторические данные не найдены")
        
        # Оставляем только нужные валюты в истории
        filtered_history = {
            date: {currency: rate for currency, rate in currencies.items() if currency in CURRENCIES}
            for date, currencies in rates.items()
        }

        return {"history": filtered_history}

# Сохранение данных в JSON файл
def save_to_json():
    with open("exchange_rates.json", "w") as file:
        json.dump(CACHED_RATES, file, ensure_ascii=False, indent=4)

@app.on_event("shutdown")
async def shutdown_event():
    save_to_json()
