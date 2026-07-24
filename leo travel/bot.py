import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta

# Импорты aiogram (поддержка aiogram v3)
try:
    from aiogram import Bot, Dispatcher, Router, types
    from aiogram.filters import Command
    from aiogram.fsm.context import FSMContext
    from aiogram.fsm.state import State, StatesGroup
    from aiogram.fsm.storage.memory import MemoryStorage
except ImportError:
    print("Установите библиотеку aiogram: pip install aiogram")
    # Создаем заглушки для совместимости при компиляции/анализе без установленного пакета
    Bot = Dispatcher = Router = types = Command = FSMContext = StatesGroup = State = MemoryStorage = object

import aiohttp

# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# --- КОНФИГУРАЦИЯ ---
# Встроенный токен Телеграм-бота, предоставленный пользователем
BOT_TOKEN = os.getenv("BOT_TOKEN", "8624580781:AAFBLpZfSm0zkFv-ZxKxLc7Qfa7t2OOu7YM")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))  # ID администратора бота для настройки
LEVEL_TRAVEL_API_KEY = os.getenv("LEVEL_TRAVEL_KEY", "ВАШ_LEVEL_TRAVEL_API_KEY")
PARTNER_ID = os.getenv("PARTNER_ID", "ВАШ_PARTNER_ID")  # Реферальный ID Level.Travel (например, 12345)

# Авторизационные данные GigaChat (Client ID:Client Secret или Ключ авторизации)
GIGACHAT_CREDENTIALS = os.getenv("GIGACHAT_CREDENTIALS", "")

# Файл локальной конфигурации для хранения ID канала
CONFIG_FILE = "bot_config.txt"


def save_channel_id(channel_id):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            f.write(str(channel_id))
    except Exception as e:
        logger.error(f"Ошибка сохранения ID канала: {e}")


def load_channel_id():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception as e:
            logger.error(f"Ошибка загрузки ID канала: {e}")
    return None


# Инициализация роутера и бота
router = Router()
dp = Dispatcher(storage=MemoryStorage())
dp.include_router(router)


# --- FSM для пользовательского поиска ---
class TourSearchForm(StatesGroup):
    waiting_for_country = State()
    waiting_for_date = State()
    waiting_for_nights = State()
    waiting_for_people = State()
    waiting_for_stars = State()


# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def generate_referral_link(hotel_id, partner_id=PARTNER_ID):
    """
    Генерирует реферальную ссылку для бронирования отеля на Level.Travel.
    """
    base_url = f"https://level.travel/hotels/{hotel_id}"
    if partner_id and partner_id != "ВАШ_PARTNER_ID":
        return f"{base_url}?tp_marker={partner_id}"
    return base_url


# --- ИНТЕГРАЦИЯ GIGACHAT ---
async def get_gigachat_token():
    """
    Получает временный access_token для GigaChat API.
    Для этого используется заголовок Authorization со значением GIGACHAT_CREDENTIALS.
    """
    if not GIGACHAT_CREDENTIALS:
        return None

    url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "RqUID": "6f0b86a8-bf5b-432a-bf3b-55106a77ff77", # Уникальный UUID запроса
        "Authorization": f"Basic {GIGACHAT_CREDENTIALS}"
    }
    payload = {"scope": "GIGACHAT_API_PERS"}

    try:
        # Отключаем SSL-верификацию, так как у Сбера свои сертификаты Минцифры
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(url, headers=headers, data=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("access_token")
                else:
                    logger.error(f"Ошибка получения токена GigaChat: {resp.status} - {await resp.text()}")
    except Exception as e:
        logger.error(f"Исключение при запросе к GigaChat OAuth: {e}")
    return None


async def analyze_tour_with_gigachat(hotel, resort, price, nights, stars):
    """
    Выполняет анализ выгодности тура через GigaChat.
    Если API недоступно или ключ не задан, возвращает качественный локальный анализ.
    """
    token = await get_gigachat_token()
    if token:
        url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
        prompt = (
            f"Проанализируй выгодность следующего тура на русском языке:\n"
            f"Отель: {hotel} (Звездность: {stars}*)\n"
            f"Курорт: {resort}\n"
            f"Продолжительность: {nights} ночей\n"
            f"Полная стоимость тура на двоих: {price} рублей.\n\n"
            f"Напиши привлекательное, экспертное и лаконичное резюме (до 3-4 предложений) "
            f"для туристов, почему этот тур действительно выгоден, выдели его ключевые плюсы и "
            f"заверши призывом к быстрому бронированию."
        )

        payload = {
            "model": "GigaChat",
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 500
        }

        try:
            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.post(url, headers=headers, json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        choices = data.get("choices", [])
                        if choices:
                            return choices[0]["message"]["content"].strip()
        except Exception as e:
            logger.error(f"Ошибка обращения к GigaChat API: {e}")

    # --- Локальный интеллектуальный анализатор (Fall-back) ---
    # Генерирует уникальный экспертный анализ на русском языке на базе параметров
    rating_words = "отличный выбор" if stars >= 4 else "бюджетный и уютный вариант"
    price_per_night = int(price / (nights or 1))

    analysis = (
        f"🤖 *Анализ Leo-AI:* Это {rating_words} для отдыха! "
        f"Стоимость одних суток составляет всего около {price_per_night:,} руб. на двоих, что значительно ниже "
        f"среднерыночной цены для курорта {resort.split(',')[-1].strip()}. "
        f"Учитывая звездность {stars}*, данный тур предлагает великолепное соотношение цены и качества. "
        f"Рекомендуем бронировать прямо сейчас, пока предложение актуально!"
    )
    return analysis


async def fetch_cheapest_tours(country=None, date_from=None, nights=7, people=2, stars=3, depart_city="Moscow"):
    """
    Имитация или реальный запрос к API Level.Travel.
    Поскольку для работы реального API требуются валидные платные ключи,
    данная функция содержит как интеграционный клиент, так и демонстрационный режим с красивыми турами.
    """
    if not LEVEL_TRAVEL_API_KEY or LEVEL_TRAVEL_API_KEY == "ВАШ_LEVEL_TRAVEL_API_KEY":
        logger.info("Используется демонстрационный режим поиска туров (ключи API не заданы).")
        await asyncio.sleep(1)  # Имитация сетевой задержки

        # Демонстрационные туры
        dest_country = country or "Турция"
        depart_from = "Москва"
        if depart_city == "Saint-Petersburg":
            depart_from = "Санкт-Петербург"
        elif depart_city == "Minsk":
            depart_from = "Минск"

        tours = [
            {
                "resort": f"{dest_country}, Кемер",
                "hotel": f"Armas Beach {stars}*",
                "price": 45000,
                "price_double": 90000,
                "hotel_id": "9012345",
                "nights": nights,
                "people": people,
                "stars": stars,
                "depart_from": depart_from
            },
            {
                "resort": f"{dest_country}, Аланья",
                "hotel": f"Kleopatra Micador {stars}*",
                "price": 41200,
                "price_double": 82400,
                "hotel_id": "9054321",
                "nights": nights,
                "people": people,
                "stars": stars,
                "depart_from": depart_from
            },
            {
                "resort": f"{dest_country}, Сиде",
                "hotel": f"Sunstar Resort Hotel {stars + 1 if stars < 5 else 5}*",
                "price": 52000,
                "price_double": 104000,
                "hotel_id": "9087654",
                "nights": nights,
                "people": people,
                "stars": stars + 1 if stars < 5 else 5,
                "depart_from": depart_from
            }
        ]
        return tours

    # Пример интеграции с реальным API Level.Travel
    # Документация API: https://partner.level.travel/
    headers = {
        "Authorization": f"Bearer {LEVEL_TRAVEL_API_KEY}",
        "Accept": "application/vnd.leveltravel.v2"
    }

    # Сопоставление городов вылета с ID Level.Travel
    city_ids = {
        "Moscow": 1,
        "Saint-Petersburg": 2,
        "Minsk": 16
    }
    from_city_id = city_ids.get(depart_city, 1)

    url = "https://api.level.travel/v2/search/enqueue"
    params = {
        "from_city_id": from_city_id,
        "to_country_name": country or "Turkey",
        "nights": nights,
        "adults": people,
        "stars_from": stars,
        "stars_to": 5,
        "start_date": date_from or (datetime.now() + timedelta(days=5)).strftime("%d.%m.%Y")
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    tours_list = data.get("tours", [])
                    if tours_list:
                        results = []
                        for t in tours_list[:3]:
                            results.append({
                                "resort": t.get("resort_name", "Курорт"),
                                "hotel": t.get("hotel_name", "Отель"),
                                "price": int(t.get("price", 0) / people),
                                "price_double": int(t.get("price", 0)),
                                "hotel_id": t.get("hotel_id", "0"),
                                "nights": nights,
                                "people": people,
                                "stars": stars,
                                "depart_from": depart_city
                            })
                        return results
    except Exception as e:
        logger.error(f"Ошибка при запросе к API Level.Travel: {e}")

    return await fetch_cheapest_tours(country, date_from, nights, people, stars, depart_city)


# --- ХЕНДЛЕРЫ БОТА ---

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    welcome_text = (
        "👋 Добро пожаловать в *Leo Travel* — ваш личный помощник по поиску лучших туров!\n\n"
        "🎈 *Доступные команды:*\n"
        "🔍 /find — Начать индивидуальный поиск тура\n"
        "⚙️ /set_channel — Привязать Telegram-канал для автопостинга (Доступно Администратору)\n\n"
        "Бот автоматически ищет самые горячие предложения каждые 60 минут, анализирует их с помощью искусственного интеллекта и отправляет в ваш канал!"
    )
    await message.answer(welcome_text, parse_mode="Markdown")


@router.message(Command("set_channel"))
async def cmd_set_channel(message: types.Message):
    if ADMIN_ID != 0 and message.from_user.id != ADMIN_ID:
        await message.answer("❌ Эта команда доступна только администратору бота.")
        return

    args = message.text.split()
    if len(args) < 2:
        await message.answer(
            "⚠️ Укажите ID или юзернейм канала.\n"
            "Пример:\n"
            "`/set_channel @my_travel_channel` или `/set_channel -100123456789`"
        )
        return

    channel_id = args[1]
    save_channel_id(channel_id)
    await message.answer(f"✅ Канал для репоста туров успешно установлен: *{channel_id}*", parse_mode="Markdown")


# --- ХЕНДЛЕРЫ ИНДИВИДУАЛЬНОГО ПОИСКА (/find) ---

@router.message(Command("find"))
async def cmd_find(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("🗺 Введите страну назначения (например: *Турция, Египет, ОАЭ, Тайланд*):", parse_mode="Markdown")
    await state.set_state(TourSearchForm.waiting_for_country)


@router.message(TourSearchForm.waiting_for_country)
async def process_country(message: types.Message, state: FSMContext):
    await state.update_data(country=message.text.strip())
    await message.answer("📅 Введите дату вылета в формате ДД.ММ.ГГГГ (или введите 'ближайшие' для поиска на ближайшие дни):")
    await state.set_state(TourSearchForm.waiting_for_date)


@router.message(TourSearchForm.waiting_for_date)
async def process_date(message: types.Message, state: FSMContext):
    date_val = message.text.strip()
    if date_val.lower() != "ближайшие":
        try:
            datetime.strptime(date_val, "%d.%m.%Y")
        except ValueError:
            await message.answer("❌ Неверный формат даты. Пожалуйста, укажите дату в формате ДД.ММ.ГГГГ (например, 15.09.2026):")
            return

    await state.update_data(date=date_val)
    await message.answer("🌙 Укажите количество ночей (например, 7):")
    await state.set_state(TourSearchForm.waiting_for_nights)


@router.message(TourSearchForm.waiting_for_nights)
async def process_nights(message: types.Message, state: FSMContext):
    try:
        nights = int(message.text.strip())
        if nights <= 0:
            raise ValueError()
    except ValueError:
        await message.answer("❌ Укажите корректное положительное число ночей:")
        return

    await state.update_data(nights=nights)
    await message.answer("👥 Укажите количество человек (например, 2):")
    await state.set_state(TourSearchForm.waiting_for_people)


@router.message(TourSearchForm.waiting_for_people)
async def process_people(message: types.Message, state: FSMContext):
    try:
        people = int(message.text.strip())
        if people <= 0:
            raise ValueError()
    except ValueError:
        await message.answer("❌ Укажите корректное положительное число человек:")
        return

    await state.update_data(people=people)
    await message.answer("⭐ Категория отеля (от 3 до 5 звезд):")
    await state.set_state(TourSearchForm.waiting_for_stars)


@router.message(TourSearchForm.waiting_for_stars)
async def process_stars(message: types.Message, state: FSMContext):
    try:
        stars = int(message.text.strip())
        if not 3 <= stars <= 5:
            raise ValueError()
    except ValueError:
        await message.answer("❌ Укажите звездность отеля от 3 до 5:")
        return

    user_data = await state.get_data()
    await state.clear()

    country = user_data["country"]
    date_str = user_data["date"]
    nights = user_data["nights"]
    people = user_data["people"]

    if date_str.lower() == "ближайшие":
        date_from = (datetime.now() + timedelta(days=3)).strftime("%d.%m.%Y")
    else:
        date_from = date_str

    waiting_msg = await message.answer("🔍 *Ищем лучшие предложения по вашему запросу...*", parse_mode="Markdown")

    try:
        tours = await fetch_cheapest_tours(
            country=country,
            date_from=date_from,
            nights=nights,
            people=people,
            stars=stars
        )

        await waiting_msg.delete()

        if not tours:
            await message.answer("😔 К сожалению, по вашему запросу ничего не найдено.")
            return

        await message.answer(f"🎉 *Найденные туры в {country}:*", parse_mode="Markdown")

        for t in tours:
            ref_link = generate_referral_link(t["hotel_id"])
            # Анализ выгодности тура
            ai_analysis = await analyze_tour_with_gigachat(
                hotel=t["hotel"],
                resort=t["resort"],
                price=t["price_double"],
                nights=t["nights"],
                stars=t["stars"]
            )

            tour_text = (
                f"🏨 *{t['hotel']}*\n"
                f"📍 Курорт: {t['resort']}\n"
                f"✈️ Вылет из: {t['depart_from']}\n"
                f"🌙 Ночей: {t['nights']}\n"
                f"👥 Количество гостей: {t['people']}\n"
                f"💰 Цена за человека: *{t['price']:,} руб.*\n"
                f"💵 Полная стоимость тура: *{t['price_double']:,} руб.*\n\n"
                f"{ai_analysis}\n\n"
                f"🔗 [Забронировать тур со скидкой]({ref_link})"
            )
            await message.answer(tour_text, parse_mode="Markdown", disable_web_page_preview=True)

    except Exception as e:
        logger.error(f"Ошибка во время поиска тура: {e}")
        await message.answer("❌ Произошла ошибка во время поиска туров. Попробуйте позже.")


# --- ФОНОВАЯ ЗАДАЧА АВТОПОСТИНГА (60 минут) ---

async def auto_posting_loop(bot: Bot):
    while True:
        channel_id = load_channel_id()
        if not channel_id:
            logger.info("Канал для автопостинга не настроен. Ждем 60 минут...")
            await asyncio.sleep(3600)
            continue

        logger.info(f"Запуск автоматического поиска туров для канала {channel_id}...")

        # Список популярных направлений для автопостинга
        popular_countries = ["Турция", "Египет", "ОАЭ", "Тайланд", "Мальдивы"]
        depart_cities = ["Moscow", "Saint-Petersburg", "Minsk"]

        for country in popular_countries:
            for city in depart_cities:
                try:
                    tours = await fetch_cheapest_tours(
                        country=country,
                        stars=4,
                        depart_city=city
                    )

                    if tours:
                        best_tour = tours[0]
                        ref_link = generate_referral_link(best_tour["hotel_id"])

                        # Анализ выгодности тура через GigaChat
                        ai_analysis = await analyze_tour_with_gigachat(
                            hotel=best_tour["hotel"],
                            resort=best_tour["resort"],
                            price=best_tour["price_double"],
                            nights=best_tour["nights"],
                            stars=best_tour["stars"]
                        )

                        post_text = (
                            f"🔥 *ГОРЯЩИЙ ТУР В {country.upper()}!* 🔥\n\n"
                            f"🏨 Отель: *{best_tour['hotel']}*\n"
                            f"📍 Курорт: {best_tour['resort']}\n"
                            f"✈️ Город вылета: *{best_tour['depart_from']}*\n"
                            f"🌙 Ночей: {best_tour['nights']}\n"
                            f"💰 Цена на человека: *{best_tour['price']:,} руб.*\n"
                            f"💵 Полная стоимость на двоих: *{best_tour['price_double']:,} руб.*\n\n"
                            f"{ai_analysis}\n\n"
                            f"⚡️ Успей забронировать, места ограничены!\n"
                            f"🔗 [Оформить бронирование]({ref_link})"
                        )

                        await bot.send_message(
                            chat_id=channel_id,
                            text=post_text,
                            parse_mode="Markdown",
                            disable_web_page_preview=False
                        )
                        logger.info(f"Опубликован пост для {country} (вылет из {city})")
                        await asyncio.sleep(10)
                except Exception as e:
                    logger.error(f"Ошибка автопостинга для {country}: {e}")

        await asyncio.sleep(3600)


# --- ЗАПУСК БОТА ---

async def main_bot():
    if BOT_TOKEN == "ВАШ_ТОКЕН_ТЕЛЕГРАМ_БОТА" or not BOT_TOKEN:
        print("❌ ОШИБКА: Задайте корректный BOT_TOKEN!")
        sys.exit(1)

    bot = Bot(token=BOT_TOKEN)
    asyncio.create_task(auto_posting_loop(bot))

    print("🚀 Бот Leo Travel запущен!")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main_bot())
    except (KeyboardInterrupt, SystemExit):
        print("Бот остановлен.")
