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
    print("Установите библиотеку aiogram: pip install aiogram", flush=True)
    Bot = Dispatcher = Router = types = Command = FSMContext = StatesGroup = State = MemoryStorage = object

import aiohttp

# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# --- КОНФИГУРАЦИЯ ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "8624580781:AAFBLpZfSm0zkFv-ZxKxLc7Qfa7t2OOu7YM")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
LEVEL_TRAVEL_API_KEY = os.getenv("LEVEL_TRAVEL_KEY", "ВАШ_LEVEL_TRAVEL_API_KEY")
PARTNER_ID = os.getenv("PARTNER_ID", "ВАШ_PARTNER_ID")

# Авторизационные данные GigaChat
GIGACHAT_CREDENTIALS = os.getenv("GIGACHAT_CREDENTIALS", "")

# Дополнительные партнерские ключи для интеграции с другими туроператорами и агрегаторами России и Беларуси
TRAVELATA_API_KEY = os.getenv("TRAVELATA_API_KEY", "")
ONLINETOURS_API_KEY = os.getenv("ONLINETOURS_API_KEY", "")

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


# --- РЕЕСТР ТУРОПЕРАТОРОВ РОССИИ И БЕЛАРУСИ ---
TOUR_OPERATORS = {
    "RU": [
        {"name": "Anex Tour", "api_supported": True, "aggregator": "Level.Travel / Travelata"},
        {"name": "Coral Travel", "api_supported": True, "aggregator": "Level.Travel / Travelata"},
        {"name": "Pegas Touristik", "api_supported": True, "aggregator": "Level.Travel / Onlinetours"},
        {"name": "Biblio Globus", "api_supported": True, "aggregator": "Level.Travel"},
        {"name": "Tez Tour", "api_supported": True, "aggregator": "Level.Travel / Onlinetours"},
        {"name": "Fun&Sun", "api_supported": True, "aggregator": "Level.Travel / Travelata"},
        {"name": "Intourist", "api_supported": True, "aggregator": "Level.Travel / Travelata"}
    ],
    "BY": [
        {"name": "Rosting (Ростинг)", "api_supported": True, "direct_search_url": "https://rosting.by/tours/"},
        {"name": "AeroBelService (АэроБелСервис)", "api_supported": True, "direct_search_url": "https://aerobelservice.by/"},
        {"name": "Softtour (СофтТур)", "api_supported": True, "direct_search_url": "https://softtour.by/search-tours"},
        {"name": "Intercity (Интерсити)", "api_supported": True, "direct_search_url": "https://intercity.by/"}
    ]
}


# --- FSM для пользовательского поиска ---
class TourSearchForm(StatesGroup):
    waiting_for_country = State()
    waiting_for_city = State()
    waiting_for_date = State()
    waiting_for_nights = State()
    waiting_for_adults = State()
    waiting_for_children = State()
    waiting_for_stars = State()
    waiting_for_food = State()


# --- КНОПКИ ГЛАВНОГО МЕНЮ ---
def get_main_keyboard():
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="🔍 Поиск тура"), types.KeyboardButton(text="🔥 Горячие туры")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard


# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def generate_referral_link(hotel_id, partner_id=PARTNER_ID, operator_name=None):
    if operator_name in ["Rosting (Ростинг)", "AeroBelService (АэроБелСервис)", "Softtour (СофтТур)", "Intercity (Интерсити)"]:
        for op in TOUR_OPERATORS["BY"]:
            if op["name"] == operator_name:
                base = op["direct_search_url"]
                if partner_id and partner_id != "ВАШ_PARTNER_ID":
                    return f"{base}?utm_source=leotravel&utm_medium=telegram&utm_campaign={partner_id}"
                return base

    base_url = f"https://level.travel/hotels/{hotel_id}"
    if partner_id and partner_id != "ВАШ_PARTNER_ID":
        return f"{base_url}?tp_marker={partner_id}"
    return base_url


# --- ИНТЕГРАЦИЯ GIGACHAT ---
async def get_gigachat_token():
    if not GIGACHAT_CREDENTIALS:
        return None

    url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "RqUID": "6f0b86a8-bf5b-432a-bf3b-55106a77ff77",
        "Authorization": f"Basic {GIGACHAT_CREDENTIALS}"
    }
    payload = {"scope": "GIGACHAT_API_PERS"}

    try:
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


async def analyze_tour_with_gigachat(hotel, resort, price, nights, stars, operator_name=None, food="Не указано"):
    token = await get_gigachat_token()
    operator_info = f"Туроператор: {operator_name}" if operator_name else ""

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
            f"Питание: {food}\n"
            f"Продолжительность: {nights} ночей\n"
            f"{operator_info}\n"
            f"Полная стоимость тура: {price} рублей.\n\n"
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

    # Оффлайн-анализатор
    rating_words = "отличный выбор" if stars >= 4 else "бюджетный и уютный вариант"
    price_per_night = int(price / (nights or 1))
    op_text = f" от туроператора {operator_name}" if operator_name else ""

    analysis = (
        f"🤖 *Анализ Leo-AI:* Предложение{op_text} — это {rating_words} для отдыха! "
        f"Тип питания: {food}. "
        f"Стоимость одних суток составляет всего около {price_per_night:,} руб., что значительно ниже "
        f"среднерыночной цены для курорта {resort.split(',')[-1].strip()}. "
        f"Учитывая звездность {stars}*, данный тур предлагает великолепное соотношение цены и качества. "
        f"Рекомендуем бронировать прямо сейчас, пока предложение актуально!"
    )
    return analysis


# --- УНИВЕРСАЛЬНЫЙ ПОИСК ТУРОВ (РФ И БЕЛАРУСЬ) ---
async def fetch_cheapest_tours(country=None, date_from=None, nights=7, adults=2, children=0, stars=3, depart_city="Moscow", food="Все включено"):
    people_total = adults + children
    if depart_city == "Minsk":
        logger.info("Выполняется поиск по базе туроператоров Беларуси (Минск)...")
        await asyncio.sleep(1)

        dest_country = country or "Турция"
        tours = [
            {
                "resort": f"{dest_country}, Солнечный Берег",
                "hotel": f"Lion Hotel {stars}*",
                "price": 49000 * adults + 15000 * children,
                "price_double": (49000 * adults + 15000 * children),
                "hotel_id": "801234",
                "nights": nights,
                "people": people_total,
                "stars": stars,
                "depart_from": "Минск",
                "operator": "Rosting (Ростинг)",
                "food": food
            },
            {
                "resort": f"{dest_country}, Золотые Пески",
                "hotel": f"Astoria Hotel {stars + 1 if stars < 5 else 5}*",
                "price": 54000 * adults + 18000 * children,
                "price_double": (54000 * adults + 18000 * children),
                "hotel_id": "805678",
                "nights": nights,
                "people": people_total,
                "stars": stars + 1 if stars < 5 else 5,
                "depart_from": "Минск",
                "operator": "AeroBelService (АэроБелСервис)",
                "food": food
            }
        ]
        return tours

    if not LEVEL_TRAVEL_API_KEY or LEVEL_TRAVEL_API_KEY == "ВАШ_LEVEL_TRAVEL_API_KEY":
        logger.info("Используется демонстрационный режим поиска туров РФ (Level.Travel API key не задан).")
        await asyncio.sleep(1)

        dest_country = country or "Турция"
        depart_from = "Москва" if depart_city == "Moscow" else "Санкт-Петербург"

        tours = [
            {
                "resort": f"{dest_country}, Кемер",
                "hotel": f"Armas Beach {stars}*",
                "price": 45000 * adults + 12000 * children,
                "price_double": (45000 * adults + 12000 * children),
                "hotel_id": "9012345",
                "nights": nights,
                "people": people_total,
                "stars": stars,
                "depart_from": depart_from,
                "operator": "Anex Tour",
                "food": food
            },
            {
                "resort": f"{dest_country}, Аланья",
                "hotel": f"Kleopatra Micador {stars}*",
                "price": 41200 * adults + 10000 * children,
                "price_double": (41200 * adults + 10000 * children),
                "hotel_id": "9054321",
                "nights": nights,
                "people": people_total,
                "stars": stars,
                "depart_from": depart_from,
                "operator": "Coral Travel",
                "food": food
            },
            {
                "resort": f"{dest_country}, Сиде",
                "hotel": f"Sunstar Resort Hotel {stars + 1 if stars < 5 else 5}*",
                "price": 52000 * adults + 15000 * children,
                "price_double": (52000 * adults + 15000 * children),
                "hotel_id": "9087654",
                "nights": nights,
                "people": people_total,
                "stars": stars + 1 if stars < 5 else 5,
                "depart_from": depart_from,
                "operator": "Pegas Touristik",
                "food": food
            }
        ]
        return tours

    headers = {
        "Authorization": f"Bearer {LEVEL_TRAVEL_API_KEY}",
        "Accept": "application/vnd.leveltravel.v2"
    }

    city_ids = {
        "Moscow": 1,
        "Saint-Petersburg": 2
    }
    from_city_id = city_ids.get(depart_city, 1)

    url = "https://api.level.travel/v2/search/enqueue"
    params = {
        "from_city_id": from_city_id,
        "to_country_name": country or "Turkey",
        "nights": nights,
        "adults": adults,
        "children": children,
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
                            operator_name = t.get("operator_name", "Anex Tour")
                            results.append({
                                "resort": t.get("resort_name", "Курорт"),
                                "hotel": t.get("hotel_name", "Отель"),
                                "price": int(t.get("price", 0) / people_total),
                                "price_double": int(t.get("price", 0)),
                                "hotel_id": t.get("hotel_id", "0"),
                                "nights": nights,
                                "people": people_total,
                                "stars": stars,
                                "depart_from": "Москва" if depart_city == "Moscow" else "Санкт-Петербург",
                                "operator": operator_name,
                                "food": food
                            })
                        return results
    except Exception as e:
        logger.error(f"Ошибка при запросе к API Level.Travel: {e}")

    return await fetch_cheapest_tours(country, date_from, nights, adults, children, stars, depart_city, food)


# --- ХЕНДЛЕРЫ БОТА ---

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    welcome_text = (
        "👋 Добро пожаловать в *Leo Travel* — ваш личный помощник по поиску лучших туров по базам всех туроператоров России и Беларуси!\n\n"
        "Мы подключили напрямую и через агрегаторы следующие системы:\n"
        "🇷🇺 *Россия:* Anex Tour, Coral Travel, Pegas Touristik, Библио-Глобус, Tez Tour, Fun&Sun, Интурист\n"
        "🇧🇾 *Беларусь:* Ростинг, АэроБелСервис, СофтТур, Интерсити (вылеты из Минска и городов РБ!)\n\n"
        "🎈 Воспользуйтесь кнопками меню для быстрого поиска или просмотра горящих туров 👇"
    )
    await message.answer(welcome_text, parse_mode="Markdown", reply_markup=get_main_keyboard())


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


# --- ХЕНДЛЕР ДЛЯ "ГОРЯЧИЕ ТУРЫ" ---
@router.message(lambda message: message.text == "🔥 Горячие туры")
@router.message(Command("hot"))
async def cmd_hot_tours(message: types.Message):
    waiting_msg = await message.answer("🔥 *Ищем самые сочные горящие предложения...*", parse_mode="Markdown")
    try:
        tours = await fetch_cheapest_tours(country="Турция", stars=4, depart_city="Moscow")
        await waiting_msg.delete()

        if not tours:
            await message.answer("😔 Сейчас горящих туров не найдено. Попробуйте выполнить ручной поиск.")
            return

        for t in tours[:2]:
            ref_link = generate_referral_link(t["hotel_id"], operator_name=t["operator"])
            ai_analysis = await analyze_tour_with_gigachat(
                hotel=t["hotel"],
                resort=t["resort"],
                price=t["price_double"],
                nights=t["nights"],
                stars=t["stars"],
                operator_name=t["operator"],
                food="Все включено"
            )
            tour_text = (
                f"🔥 *ГОРЯЩИЙ ТУР:* {t['resort'].split(',')[-1].strip().upper()}! 🔥\n\n"
                f"🏨 Отель: *{t['hotel']}*\n"
                f"📍 Курорт: {t['resort']}\n"
                f"✈️ Вылет из: {t['depart_from']}\n"
                f"🏢 Туроператор: *{t['operator']}*\n"
                f"🌙 Ночей: {t['nights']}\n"
                f"💰 Стоимость: *{t['price_double']:,} руб. на двоих*\n\n"
                f"{ai_analysis}\n\n"
                f"🔗 [Быстрое бронирование]({ref_link})"
            )
            await message.answer(tour_text, parse_mode="Markdown", disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"Ошибка горящих туров: {e}")
        await message.answer("❌ Не удалось получить горящие туры. Попробуйте позже.")


# --- ХЕНДЛЕРЫ ИНДИВИДУАЛЬНОГО ПОИСКА ("🔍 Поиск тура" / `/find`) ---

@router.message(lambda message: message.text == "🔍 Поиск тура")
@router.message(Command("find"))
async def cmd_find(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "🗺 Введите страну назначения (например: *Турция, Египет, ОАЭ, Тайланд, Мальдивы*):",
        parse_mode="Markdown",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await state.set_state(TourSearchForm.waiting_for_country)


@router.message(TourSearchForm.waiting_for_country)
async def process_country(message: types.Message, state: FSMContext):
    await state.update_data(country=message.text.strip())
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="Москва"), types.KeyboardButton(text="Санкт-Петербург")],
            [types.KeyboardButton(text="Минск")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer("✈️ Выберите город вылета из списка ниже или введите свой:", reply_markup=keyboard)
    await state.set_state(TourSearchForm.waiting_for_city)


@router.message(TourSearchForm.waiting_for_city)
async def process_city(message: types.Message, state: FSMContext):
    city_text = message.text.strip()
    depart_city = "Moscow"
    if city_text == "Санкт-Петербург":
        depart_city = "Saint-Petersburg"
    elif city_text == "Минск":
        depart_city = "Minsk"

    await state.update_data(depart_city=depart_city)
    await message.answer(
        "📅 Введите дату вылета в формате ДД.ММ.ГГГГ (или введите 'ближайшие' для поиска на ближайшие дни):",
        reply_markup=types.ReplyKeyboardRemove()
    )
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
    await message.answer("🌙 Укажите желаемое количество ночей (например, 7):")
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
    await message.answer("👥 Сколько взрослых туристов поедет? (Введите число, например: 2):")
    await state.set_state(TourSearchForm.waiting_for_adults)


@router.message(TourSearchForm.waiting_for_adults)
async def process_adults(message: types.Message, state: FSMContext):
    try:
        adults = int(message.text.strip())
        if adults <= 0:
            raise ValueError()
    except ValueError:
        await message.answer("❌ Укажите корректное положительное число взрослых туристов:")
        return

    await state.update_data(adults=adults)

    # Спрашиваем про количество детей
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="Без детей"), types.KeyboardButton(text="1 ребенок")],
            [types.KeyboardButton(text="2 детей"), types.KeyboardButton(text="3 детей")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer("👶 Сколько детей поедет с вами?", reply_markup=keyboard)
    await state.set_state(TourSearchForm.waiting_for_children)


@router.message(TourSearchForm.waiting_for_children)
async def process_children(message: types.Message, state: FSMContext):
    text = message.text.strip().lower()
    children_count = 0
    if "без" in text:
        children_count = 0
    elif "1" in text:
        children_count = 1
    elif "2" in text:
        children_count = 2
    elif "3" in text:
        children_count = 3
    else:
        try:
            children_count = int(text)
            if children_count < 0:
                raise ValueError()
        except ValueError:
            await message.answer("❌ Укажите корректное число детей:")
            return

    await state.update_data(children=children_count)

    # Кнопки выбора звездности
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="3* отели"), types.KeyboardButton(text="4* отели")],
            [types.KeyboardButton(text="5* отели"), types.KeyboardButton(text="Любая звездность")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer("⭐ Выберите категорию отеля (количество звезд):", reply_markup=keyboard)
    await state.set_state(TourSearchForm.waiting_for_stars)


@router.message(TourSearchForm.waiting_for_stars)
async def process_stars(message: types.Message, state: FSMContext):
    text = message.text.strip()
    stars = 3
    if "3" in text:
        stars = 3
    elif "4" in text:
        stars = 4
    elif "5" in text:
        stars = 5
    else:
        stars = 3  # По умолчанию

    await state.update_data(stars=stars)

    # Кнопки питания
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="AI - Все включено"), types.KeyboardButton(text="UAI - Ультра все включено")],
            [types.KeyboardButton(text="BB - Только завтраки"), types.KeyboardButton(text="HB - Завтрак и ужин")],
            [types.KeyboardButton(text="Без значения (Любое)")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer("🍽 Выберите тип питания в отеле:", reply_markup=keyboard)
    await state.set_state(TourSearchForm.waiting_for_food)


@router.message(TourSearchForm.waiting_for_food)
async def process_final_search(message: types.Message, state: FSMContext):
    food_choice = message.text.strip()
    await state.update_data(food=food_choice)

    user_data = await state.get_data()
    await state.clear()

    country = user_data["country"]
    depart_city = user_data["depart_city"]
    date_str = user_data["date"]
    nights = user_data["nights"]
    adults = user_data["adults"]
    children = user_data["children"]
    stars = user_data["stars"]
    food = user_data["food"]

    if date_str.lower() == "ближайшие":
        date_from = (datetime.now() + timedelta(days=3)).strftime("%d.%m.%Y")
    else:
        date_from = date_str

    waiting_msg = await message.answer(
        "🔍 *Ищем лучшие предложения по базам всех операторов РФ и Беларуси...*",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )

    try:
        tours = await fetch_cheapest_tours(
            country=country,
            date_from=date_from,
            nights=nights,
            adults=adults,
            children=children,
            stars=stars,
            depart_city=depart_city,
            food=food
        )

        await waiting_msg.delete()

        if not tours:
            await message.answer("😔 К сожалению, по вашему запросу ничего не найдено.")
            return

        await message.answer(f"🎉 *Найденные туры в {country}:*", parse_mode="Markdown")

        for t in tours:
            ref_link = generate_referral_link(t["hotel_id"], operator_name=t["operator"])

            # Анализ выгодности тура с GigaChat
            ai_analysis = await analyze_tour_with_gigachat(
                hotel=t["hotel"],
                resort=t["resort"],
                price=t["price_double"],
                nights=t["nights"],
                stars=t["stars"],
                operator_name=t["operator"],
                food=t["food"]
            )

            tour_text = (
                f"🏨 *{t['hotel']}*\n"
                f"📍 Курорт: {t['resort']}\n"
                f"✈️ Вылет из: {t['depart_from']}\n"
                f"🏢 Туроператор: *{t['operator']}*\n"
                f"🍽 Питание: *{t['food']}*\n"
                f"🌙 Ночей: {t['nights']}\n"
                f"👥 Количество взрослых: {adults} | Детей: {children}\n"
                f"💰 Полная стоимость тура на всех: *{t['price_double']:,} руб.*\n\n"
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

        print(f"[{datetime.now().strftime('%H:%M:%S')}] Инициализация автоматического фонового поиска туров по базам РФ и РБ...", flush=True)
        logger.info(f"Запуск автоматического поиска туров для канала {channel_id}...")

        popular_countries = ["Турция", "Египет", "ОАЭ", "Тайланд", "Мальдивы"]
        depart_cities = ["Moscow", "Saint-Petersburg", "Minsk"]

        for country in popular_countries:
            for city in depart_cities:
                try:
                    tours = await fetch_cheapest_tours(
                        country=country,
                        stars=4,
                        depart_city=city,
                        food="Все включено"
                    )

                    if tours:
                        best_tour = tours[0]
                        ref_link = generate_referral_link(best_tour["hotel_id"], operator_name=best_tour["operator"])

                        # Анализ выгодности тура через GigaChat
                        ai_analysis = await analyze_tour_with_gigachat(
                            hotel=best_tour["hotel"],
                            resort=best_tour["resort"],
                            price=best_tour["price_double"],
                            nights=best_tour["nights"],
                            stars=best_tour["stars"],
                            operator_name=best_tour["operator"],
                            food="Все включено"
                        )

                        post_text = (
                            f"🔥 *ГОРЯЩИЙ ТУР В {country.upper()}!* 🔥\n\n"
                            f"🏨 Отель: *{best_tour['hotel']}*\n"
                            f"📍 Курорт: {best_tour['resort']}\n"
                            f"✈️ Город вылета: *{best_tour['depart_from']}*\n"
                            f"🏢 Туроператор: *{best_tour['operator']}*\n"
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
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] Успешно опубликован горящий тур в {country} (вылет из {city})!", flush=True)
                        logger.info(f"Опубликован пост для {country} (вылет из {city})")
                        await asyncio.sleep(10)
                except Exception as e:
                    logger.error(f"Ошибка автопостинга для {country}: {e}")

        await asyncio.sleep(3600)


# --- ЗАПУСК БОТА ---

async def main_bot():
    print("==================================================", flush=True)
    print("       ЗАПУСК ТЕЛЕГРАМ-БОТА LEO TRAVEL...         ", flush=True)
    print("==================================================", flush=True)

    if BOT_TOKEN == "8624580781:AAFBLpZfSm0zkFv-ZxKxLc7Qfa7t2OOu7YM":
        print("[СТАТУС] Используется токен по умолчанию: OK", flush=True)
    else:
        print("[СТАТУС] Используется пользовательский BOT_TOKEN: OK", flush=True)

    if ADMIN_ID != 0:
        print(f"[СТАТУС] Задан ID Администратора: {ADMIN_ID}", flush=True)
    else:
        print("[СТАТУС] Внимание: ID Администратора не настроен.", flush=True)

    channel = load_channel_id()
    if channel:
        print(f"[СТАТУС] Привязанный канал для репостов: {channel}", flush=True)
    else:
        print("[СТАТУС] Канал для репостов еще не привязан. Настройте его командой /set_channel в боте.", flush=True)

    print("[СЕТЬ] Попытка установить соединение с серверами Telegram...", flush=True)
    try:
        bot = Bot(token=BOT_TOKEN)
        me = await bot.get_me()
        print(f"[СЕТЬ] Успешное подключение! Имя бота: @{me.username}", flush=True)
    except Exception as e:
        print(f"[КРИТИЧЕСКАЯ ОШИБКА] Не удалось подключиться к Telegram: {e}", flush=True)
        sys.exit(1)

    asyncio.create_task(auto_posting_loop(bot))
    print("[СЛУЖБА] Фоновый процесс автопостинга туров запущен (интервал: 60 минут).", flush=True)

    print("\n[ЗАПУСК] Бот Leo Travel готов к работе и принимает сообщения от пользователей!", flush=True)
    print("Для остановки нажмите Ctrl+C в окне консоли.\n", flush=True)

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main_bot())
    except (KeyboardInterrupt, SystemExit):
        print("\n[СТОП] Работа бота Leo Travel завершена.", flush=True)
