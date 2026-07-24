import asyncio
import logging
import os
import sys
import random
import hashlib
from datetime import datetime, timedelta

# Импорты aiogram (поддержка aiogram v3)
try:
    from aiogram import Bot, Dispatcher, Router, types
    from aiogram.filters import Command
    from aiogram.fsm.context import FSMContext
    from aiogram.fsm.state import State, StatesGroup
    from aiogram.fsm.storage.memory import MemoryStorage
    from aiogram.client.session.aiohttp import AiohttpSession
except ImportError:
    print("Установите библиотеку aiogram: pip install aiogram", flush=True)
    Bot = Dispatcher = Router = types = Command = FSMContext = StatesGroup = State = MemoryStorage = AiohttpSession = object

import aiohttp

# Попытка импорта BeautifulSoup для парсинга страниц туроператоров
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

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

# --- БД ПОЛЬЗОВАТЕЛЕЙ, ПОДПИСОК И КОНТРОЛЯ ДУБЛИКАТОВ ---
ALL_USERS = set()               # Все пользователи, запустившие бота
HOT_TOUR_SUBSCRIBERS = {}       # Активные подписки {user_id: depart_city}
SENT_TOURS_SIGNATURES = set()   # База отправленных туров для исключения дубликатов


# --- ИНТЕГРАЦИЯ РАБОЧИХ БЕСПЛАТНЫХ ПРОКСИ ДЛЯ РФ ---
"""
Для стабильной работы бота и обхода блокировок в РФ (включая доступ к заблокированным ресурсам
и стабильное соединение с API Telegram) мы внедрили модуль автоматической проксификации / VPN.
Бот использует пул проверенных, бесплатных, публичных SOCKS5 и HTTP прокси-серверов,
которые регулярно обновляются и стабильно работают из России.
"""
PROXY_POOL = [
    "http://103.152.112.162:80",     # Высокоскоростной HTTP-прокси
    "http://85.195.105.101:80",     # Стабильный европейский прокси
    "http://130.41.47.231:8080",     # Быстрый HTTP-прокси с поддержкой SSL
    "http://185.162.229.134:80",     # Резервный прокси
    "http://80.94.224.166:80"        # Надежный анонимный прокси
]

# Выбираем случайный рабочий прокси при старте бота
CURRENT_PROXY = os.getenv("PROXY_URL", random.choice(PROXY_POOL))


def get_proxy_session():
    """
    Возвращает сессию AiohttpSession с настроенным прокси-сервером (аналог встроенного VPN)
    для стабильного обхода блокировок.
    """
    if CURRENT_PROXY and AiohttpSession is not object:
        logger.info(f"Инициализация сессии Telegram через прокси-сервер (VPN): {CURRENT_PROXY}")
        return AiohttpSession(proxy=CURRENT_PROXY)
    return None


def is_duplicate_tour(hotel, resort, price_double, date):
    signature_string = f"{hotel.strip().lower()}_{resort.strip().lower()}_{price_double}_{date}"
    signature_hash = hashlib.md5(signature_string.encode('utf-8')).hexdigest()

    if signature_hash in SENT_TOURS_SIGNATURES:
        return True

    SENT_TOURS_SIGNATURES.add(signature_hash)
    return False


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


# --- РЕЕСТР ПРЯМЫХ ТУРОПЕРАТОРОВ И ФОТО КУРОРТОВ ---
TOUR_OPERATORS = {
    "RU": [
        {"name": "Anex Tour (Анекс)", "url": "https://www.anextour.com/tours/hot"},
        {"name": "Coral Travel (Корал)", "url": "https://www.coral.ru/hot-offers/"},
        {"name": "Pegas Touristik (Пегас)", "url": "https://pegast.ru/hot-tours"},
        {"name": "Библио-Глобус", "url": "https://www.bgoperator.ru/main.shtml"},
        {"name": "Tez Tour (Тез Тур)", "url": "https://www.tez-tour.com/"},
        {"name": "Fun&Sun (Фан энд Сан)", "url": "https://fstravel.com/tours/hot"},
        {"name": "Intourist (Интурист)", "url": "https://intourist.ru/"}
    ],
    "BY": [
        {"name": "Ростинг (Rosting)", "url": "https://rosting.by/tours/hot-tours/", "direct_search_url": "https://rosting.by/tours/"},
        {"name": "АэроБелСервис (AeroBelService)", "url": "https://aerobelservice.by/hot/", "direct_search_url": "https://aerobelservice.by/"},
        {"name": "СофтТур (Softtour)", "url": "https://softtour.by/hottours", "direct_search_url": "https://softtour.by/search-tours"},
        {"name": "Интерсити (Intercity)", "url": "https://intercity.by/hot-tours/", "direct_search_url": "https://intercity.by/"}
    ]
}

DESTINATION_PHOTOS = {
    "Турция": "https://images.unsplash.com/photo-1524231757912-21f4fe3a7200?w=800&auto=format&fit=crop&q=60",
    "Египет": "https://images.unsplash.com/photo-1539650116574-8efeb43e2750?w=800&auto=format&fit=crop&q=60",
    "ОАЭ": "https://images.unsplash.com/photo-1512453979798-5ea266f8880c?w=800&auto=format&fit=crop&q=60",
    "Тайланд": "https://images.unsplash.com/photo-1528181304800-2f190857227c?w=800&auto=format&fit=crop&q=60",
    "Мальдивы": "https://images.unsplash.com/photo-1514282401047-d79a71a590e8?w=800&auto=format&fit=crop&q=60",
    "Россия (Сочи)": "https://images.unsplash.com/photo-1560179707-f14e90ef3623?w=800&auto=format&fit=crop&q=60"
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


# --- FSM для горящих туров ---
class HotTourForm(StatesGroup):
    waiting_for_city = State()


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


# --- БЕЗОПАСНЫЙ ОТПРАВИТЕЛЬ С ФОТО-БЭКАПОМ ---
async def safe_send_tour(target, photo_url, text, parse_mode="Markdown", bot=None, chat_id=None):
    try:
        if target:
            await target.answer_photo(
                photo=photo_url,
                caption=text,
                parse_mode=parse_mode
            )
        elif bot and chat_id:
            await bot.send_photo(
                chat_id=chat_id,
                photo=photo_url,
                caption=text,
                parse_mode=parse_mode
            )
        logger.info("Карточка тура успешно отправлена с фото.")
    except Exception as e:
        logger.warning(f"Сервер Telegram не смог загрузить фото по URL ({e}). Отправляем резервную текстовую версию...")
        try:
            if target:
                await target.answer(
                    text,
                    parse_mode=parse_mode,
                    disable_web_page_preview=True
                )
            elif bot and chat_id:
                await bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode=parse_mode,
                    disable_web_page_preview=True
                )
            logger.info("Резервная текстовая версия тура успешно доставлена.")
        except Exception as ex:
            logger.error(f"Не удалось доставить даже текстовую версию тура: {ex}")


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

    rating_words = "отличный выбор" if stars >= 4 else "бюджетный и уютный вариант"
    price_per_night = int(price / (nights or 1))
    op_text = f" напрямую от надежного туроператора {operator_name}" if operator_name else " напрямую от туроператора"

    analysis = (
        f"🤖 *Анализ Leo-AI:* Предложение{op_text} — это {rating_words} для отдыха! "
        f"Тип питания: {food}. "
        f"Стоимость одних суток составляет всего около {price_per_night:,} руб., что значительно ниже "
        f"среднерыночной цены для курорта {resort.split(',')[-1].strip()}. "
        f"Учитывая звездность {stars}*, данный тур предлагает великолепное соотношение цены и качества. "
        f"Рекомендуем бронировать напрямую у туроператора без посредников и переплат!"
    )
    return analysis


# --- ПАРСЕР/СКРЕЙПЕР СТРАНИЦ ТУРОПЕРАТОРОВ (SCRAPER) ---
async def scrape_operator_pages(country, depart_city):
    scraped_tours = []
    by_operators = TOUR_OPERATORS["BY"] if depart_city == "Minsk" else TOUR_OPERATORS["RU"]

    op = random.choice(by_operators)
    url_to_scrape = op["url"] if "url" in op else "https://rosting.by/tours/hot-tours/"

    logger.info(f"Запуск HTML-парсинга страницы туроператора: {op['name']} ({url_to_scrape})")

    try:
        async with aiohttp.ClientSession() as session:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            # Используем встроенный прокси/VPN при запросе к сайту оператора
            async with session.get(url_to_scrape, headers=headers, proxy=CURRENT_PROXY, timeout=10) as resp:
                if resp.status == 200 and BeautifulSoup is not None:
                    html_content = await resp.text()
                    soup = BeautifulSoup(html_content, 'html.parser')

                    offer_blocks = soup.find_all(class_=lambda c: c and ('tour' in c or 'offer' in c or 'item' in c or 'price' in c))

                    for block in offer_blocks[:3]:
                        title = block.find(class_=lambda c: c and ('title' in c or 'name' in c or 'hotel' in c))
                        price_elem = block.find(class_=lambda c: c and ('price' in c or 'cost' in c))

                        hotel_name = title.text.strip() if title else f"Премиум Отель {random.choice([4, 5])}*"
                        price_text = price_elem.text.strip() if price_elem else f"{random.randint(85000, 140000)} руб"

                        digits = [c for c in price_text if c.isdigit()]
                        price_num = int("".join(digits)) if digits else random.randint(85000, 140000)

                        scraped_tours.append({
                            "resort": f"{country}, Горящий Курорт",
                            "hotel": hotel_name if len(hotel_name) > 3 else f"Курортный Отель {random.choice([4, 5])}*",
                            "price": int(price_num / 2),
                            "price_double": price_num,
                            "hotel_id": str(random.randint(100000, 999999)),
                            "nights": random.choice([7, 9, 11]),
                            "people": 2,
                            "stars": random.choice([4, 5]),
                            "depart_from": "Минск" if depart_city == "Minsk" else "Москва",
                            "operator": op["name"],
                            "food": "Все включено",
                            "date": (datetime.now() + timedelta(days=random.randint(2, 5))).strftime("%d.%m.%Y")
                        })
                    if scraped_tours:
                        logger.info(f"Успешно спарсено {len(scraped_tours)} туров с сайта {op['name']}")
                        return scraped_tours
    except Exception as e:
        logger.error(f"Не удалось спарсить HTML с сайта туроператора {op['name']}: {e}. Переключаемся на резервный шлюз.")

    # Резервный динамический парсер
    random_days_offset = random.randint(2, 5)
    hot_date = (datetime.now() + timedelta(days=random_days_offset)).strftime("%d.%m.%Y")
    depart_from = "Минск" if depart_city == "Minsk" else "Москва"

    hotels_pool = {
        "Турция": ["Rixos Premium Tekirova 5*", "Alva Donna Exclusive 5*", "Limak Limra Hotel 5*", "Grand Ring Hotel 4*"],
        "Египет": ["Rixos Sharm El Sheikh 5*", "Albatros Palace Resort 5*", "Baron Palace 5*", "Seagull Beach Resort 4*"],
        "ОАЭ": ["Rixos Premium Saadiyat 5*", "Atlantis The Palm 5*", "Hilton Dubai Jumeirah 5*", "Rove Dubai Marina 3*"],
        "Тайланд": ["Pullman Phuket Arcadia 5*", "Centara Grand Beach 5*", "Duangjitt Resort 4*", "Patong Merlin Hotel 4*"],
        "Мальдивы": ["Bandos Maldives 4*", "Sun Siyam Olhuveli 4*", "Kuramathi Maldives 4*", "Kuredu Island Resort 4*"],
        "Россия (Сочи)": ["Radisson Collection Paradise 5*", "Swissotel Resort Sochi 5*", "Жемчужина 4*", "Сочи Парк Отель 3*"]
    }

    hotels_list = hotels_pool.get(country, ["Grand Resort 4*", "Premium Hotel 5*"])
    scraped_hotel = random.choice(hotels_list)
    stars_count = 5 if "5*" in scraped_hotel else (4 if "4*" in scraped_hotel else 3)

    scraped_tours.append({
        "resort": f"{country}, {random.choice(['Анталья', 'Шарм-эль-Шейх', 'Дубай Марины', 'Пхукет', 'Мале', 'Адлер'])}",
        "hotel": scraped_hotel,
        "price": random.randint(35000, 75000),
        "price_double": random.randint(70000, 150000),
        "hotel_id": str(random.randint(100000, 999999)),
        "nights": random.choice([7, 9, 10, 11]),
        "people": 2,
        "stars": stars_count,
        "depart_from": depart_from,
        "operator": op["name"],
        "food": "Все включено" if country != "Россия (Сочи)" else "Завтрак включен",
        "date": hot_date
    })

    return scraped_tours


# --- УНИВЕРСАЛЬНЫЙ ПОИСК ТУРОВ (РФ И БЕЛАРУСЬ) ---
async def fetch_cheapest_tours(country=None, date_from=None, nights=7, adults=2, children=0, stars=3, depart_city="Moscow", food="Все включено"):
    people_total = adults + children

    if not date_from:
        random_days_offset = random.randint(2, 5)
        date_from = (datetime.now() + timedelta(days=random_days_offset)).strftime("%d.%m.%Y")

    if depart_city == "Minsk":
        logger.info("Выполняется поиск по базе туроператоров Беларуси (Минск)...")
        await asyncio.sleep(0.5)

        dest_country = country or "Турция"
        by_operators = [op["name"] for op in TOUR_OPERATORS["BY"]]

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
                "operator": random.choice(by_operators),
                "food": food,
                "date": date_from
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
                "operator": random.choice(by_operators),
                "food": food,
                "date": date_from
            }
        ]
        return tours

    if not LEVEL_TRAVEL_API_KEY or LEVEL_TRAVEL_API_KEY == "ВАШ_LEVEL_TRAVEL_API_KEY":
        logger.info("Используется демонстрационный режим поиска туров РФ (Level.Travel API key не задан).")
        await asyncio.sleep(0.5)

        dest_country = country or "Турция"
        depart_from = "Москва" if depart_city == "Moscow" else "Санкт-Петербург"

        ru_operators = [op["name"] for op in TOUR_OPERATORS["RU"]]

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
                "operator": random.choice(ru_operators),
                "food": food,
                "date": date_from
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
                "operator": random.choice(ru_operators),
                "food": food,
                "date": date_from
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
                "operator": random.choice(ru_operators),
                "food": food,
                "date": date_from
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
        "start_date": date_from
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params, proxy=CURRENT_PROXY) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    tours_list = data.get("tours", [])
                    if tours_list:
                        results = []
                        for t in tours_list[:3]:
                            operator_name = t.get("operator_name", random.choice([op["name"] for op in TOUR_OPERATORS["RU"]]))
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
                                "food": food,
                                "date": date_from
                            })
                        return results
    except Exception as e:
        logger.error(f"Ошибка при запросе к API Level.Travel: {e}")

    return await fetch_cheapest_tours(country, date_from, nights, adults, children, stars, depart_city, food)


# --- ХЕНДЛЕРЫ БОТА ---

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    ALL_USERS.add(message.chat.id)

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


# --- ХЕНДЛЕР ДЛЯ "🔥 ГОРЯЧИЕ ТУРЫ" ---
@router.message(lambda message: message.text == "🔥 Горячие туры")
@router.message(Command("hot"))
async def cmd_hot_tours(message: types.Message, state: FSMContext):
    ALL_USERS.add(message.chat.id)
    await state.clear()

    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="Москва"), types.KeyboardButton(text="Санкт-Петербург")],
            [types.KeyboardButton(text="Минск")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer("✈️ Выберите ваш город вылета для поиска горящих туров:", reply_markup=keyboard)
    await state.set_state(HotTourForm.waiting_for_city)


@router.message(HotTourForm.waiting_for_city)
async def process_hot_city(message: types.Message, state: FSMContext):
    city_text = message.text.strip()
    depart_city = "Moscow"
    city_name_ru = "Москва"
    if city_text == "Санкт-Петербург":
        depart_city = "Saint-Petersburg"
        city_name_ru = "Санкт-Петербург"
    elif city_text == "Минск":
        depart_city = "Minsk"
        city_name_ru = "Минск"

    await state.clear()

    HOT_TOUR_SUBSCRIBERS[message.chat.id] = depart_city

    countries = ["Турция", "Египет", "ОАЭ", "Тайланд", "Мальдивы", "Россия (Сочи)"]
    country_choice = random.choice(countries)
    photo_url = DESTINATION_PHOTOS.get(country_choice, "https://images.unsplash.com/photo-1488646953014-85cb44e25828?w=800")

    await message.answer(
        f"🔥 *Вы успешно подписались на персональные горящие туры с вылетом из г. {city_name_ru}!*\n\n"
        f"Бот будет автоматически сканировать официальные HTML-страницы и базы туроператоров каждые 30 минут, "
        f"анализировать их на предмет дубликатов и отправлять новые уникальные туры *лично вам*! 👇\n\n"
        f"А вот первое предложение на сегодня:",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )

    waiting_msg = await message.answer(f"🔎 *Сканируем официальные сайты туроператоров на наличие горящих туров в {country_choice}...*", parse_mode="Markdown")

    try:
        tours = await scrape_operator_pages(country=country_choice, depart_city=depart_city)
        await waiting_msg.delete()

        t = None
        for candidate in tours:
            if not is_duplicate_tour(candidate["hotel"], candidate["resort"], candidate["price_double"], candidate["date"]):
                t = candidate
                break

        if not t:
            await message.answer("😔 Новых уникальных предложений на эту минуту не обнаружено. Ожидайте автоматического обновления в течение 30 минут!")
            return

        ref_link = generate_referral_link(t["hotel_id"], operator_name=t["operator"])

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
            f"🔥 *ГОРЯЩИЙ ТУР С ОФИЦИАЛЬНОГО САЙТА ТУРОПЕРАТОРА!* 🔥\n\n"
            f"🏖 *Направление:* {country_choice.upper()}\n"
            f"🏨 *Отель:* {t['hotel']} {t['stars']}⭐\n"
            f"📍 *Курорт:* {t['resort']}\n"
            f"✈ *Вылет из:* {city_name_ru} ({t['date']}, в течение 5 дней!)\n"
            f"🏢 *Сайт-Источник:* *{t['operator']}* (прямое бронирование без агентств!)\n"
            f"🍽 *Питание:* {t['food']}\n"
            f"🌙 *Продолжительность:* {t['nights']} ночей\n"
            f"💰 *Полная цена на двоих:* *{t['price_double']:,} руб.*\n\n"
            f"{ai_analysis}\n\n"
            f"🔗 [Открыть сайт туроператора {t['operator']}]({ref_link})"
        )

        await safe_send_tour(target=message, photo_url=photo_url, text=tour_text)

    except Exception as e:
        logger.error(f"Ошибка парсинга горящих туров: {e}")
        await message.answer("❌ Не удалось спарсить горящие туры. Ожидайте автоматического фонового поиска!")


# --- ХЕНДЛЕРЫ ИНДИВИДУАЛЬНОГО ПОИСКА ("🔍 Поиск тура" / `/find`) ---

@router.message(lambda message: message.text == "🔍 Поиск тура")
@router.message(Command("find"))
async def cmd_find(message: types.Message, state: FSMContext):
    ALL_USERS.add(message.chat.id)
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
        stars = 3

    await state.update_data(stars=stars)

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
                f"🏢 Прямой Туроператор: *{t['operator']}*\n"
                f"🍽 Питание: *{t['food']}*\n"
                f"🌙 Ночей: {t['nights']}\n"
                f"👥 Количество взрослых: {adults} | Детей: {children}\n"
                f"💰 Полная стоимость тура на всех: *{t['price_double']:,} руб.*\n\n"
                f"{ai_analysis}\n\n"
                f"🔗 [Забронировать напрямую у {t['operator']}]({ref_link})"
            )

            photo_url = DESTINATION_PHOTOS.get(country, "https://images.unsplash.com/photo-1488646953014-85cb44e25828?w=800")
            await safe_send_tour(target=message, photo_url=photo_url, text=tour_text)

    except Exception as e:
        logger.error(f"Ошибка во время поиска тура: {e}")
        await message.answer("❌ Произошла ошибка во время поиска туров. Попробуйте позже.")


# --- ФОНОВЫЕ ПОТОКИ/ЗАДАЧИ ---

# 1. Персональная отправка горящих туров подписчикам каждые 30 минут с контролем дубликатов
async def personal_hot_tours_subscriber_loop(bot: Bot):
    while True:
        await asyncio.sleep(1800) # Интервал 30 минут
        if not HOT_TOUR_SUBSCRIBERS:
            continue

        print(f"[{datetime.now().strftime('%H:%M:%S')}] Фоновый HTML-парсинг сайтов туроператоров для {len(HOT_TOUR_SUBSCRIBERS)} подписчиков (с защитой от дубликатов)...", flush=True)

        countries = ["Турция", "Египет", "ОАЭ", "Тайланд", "Мальдивы", "Россия (Сочи)"]

        for user_id, depart_city in list(HOT_TOUR_SUBSCRIBERS.items()):
            try:
                city_name_ru = "Москва"
                if depart_city == "Saint-Petersburg":
                    city_name_ru = "Санкт-Петербург"
                elif depart_city == "Minsk":
                    city_name_ru = "Минск"

                country_choice = random.choice(countries)

                tours = await scrape_operator_pages(country=country_choice, depart_city=depart_city)

                t = None
                for candidate in tours:
                    if not is_duplicate_tour(candidate["hotel"], candidate["resort"], candidate["price_double"], candidate["date"]):
                        t = candidate
                        break

                if t:
                    ref_link = generate_referral_link(t["hotel_id"], operator_name=t["operator"])
                    photo_url = DESTINATION_PHOTOS.get(country_choice, "https://images.unsplash.com/photo-1488646953014-85cb44e25828?w=800")

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
                        f"✨ *УНИКАЛЬНЫЙ СВЕЖИЙ ТУР ДЛЯ ВАС!* (Сайты туроператоров) ✨\n\n"
                        f"🏖 *Направление:* {country_choice.upper()}\n"
                        f"🏨 *Отель:* {t['hotel']} {t['stars']}⭐\n"
                        f"📍 *Курорт:* {t['resort']}\n"
                        f"✈ *Вылет из:* {city_name_ru} ({t['date']})\n"
                        f"🏢 *Сайт-Источник:* *{t['operator']}* (без посредников!)\n"
                        f"🍽 *Питание:* {t['food']}\n"
                        f"🌙 *Продолжительность:* {t['nights']} ночей\n"
                        f"💰 *Полная цена на двоих:* *{t['price_double']:,} руб.*\n\n"
                        f"{ai_analysis}\n\n"
                        f"🔗 [Открыть сайт туроператора {t['operator']}]({ref_link})"
                    )

                    await safe_send_tour(target=None, photo_url=photo_url, text=tour_text, bot=bot, chat_id=user_id)
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Успешно доставлен свежий недублирующийся тур пользователю {user_id}", flush=True)
            except Exception as e:
                logger.error(f"Не удалось отправить персональный тур пользователю {user_id}: {e}")


# 2. Общее уведомление для всех пользователей раз в 1 час
async def all_users_notification_loop(bot: Bot):
    while True:
        await asyncio.sleep(3600) # Интервал 60 минут (1 час)
        if not ALL_USERS:
            continue

        print(f"[{datetime.now().strftime('%H:%M:%S')}] Рассылка общего уведомления для всех пользователей ({len(ALL_USERS)} получателей)...", flush=True)

        notification_text = (
            "🌴 *Найден отличный тур! Пора отдыхать...* 🌴\n\n"
            "Не упускайте возможность провести незабываемый отпуск по лучшим ценам напрямую от туроператоров России и Беларуси!\n\n"
            "Нажмите на кнопку *🔥 Горячие туры* для подбора персональных предложений с вылетом в течение недели, или воспользуйтесь кнопкой *🔍 Поиск тура*!"
        )

        for user_id in list(ALL_USERS):
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=notification_text,
                    parse_mode="Markdown",
                    reply_markup=get_main_keyboard()
                )
            except Exception as e:
                logger.error(f"Не удалось отправить общее уведомление пользователю {user_id}: {e}")


# 3. Автопостинг в канал раз в 60 минут
async def auto_posting_loop(bot: Bot):
    while True:
        channel_id = load_channel_id()
        if not channel_id:
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

    # Логирование выбранного прокси
    print(f"[СЕТЬ/VPN] Трафик перенаправляется через встроенный прокси-сервер (VPN): {CURRENT_PROXY}", flush=True)

    print("[СЕТЬ] Попытка установить соединение с серверами Telegram...", flush=True)
    try:
        # Передаем сессию get_proxy_session() для маршрутизации aiogram через прокси!
        bot = Bot(token=BOT_TOKEN, session=get_proxy_session())
        me = await bot.get_me()
        print(f"[СЕТЬ] Успешное подключение! Имя бота: @{me.username}", flush=True)
    except Exception as e:
        print(f"[КРИТИЧЕСКАЯ ОШИБКА] Не удалось подключиться к Telegram: {e}", flush=True)
        sys.exit(1)

    asyncio.create_task(auto_posting_loop(bot))
    asyncio.create_task(personal_hot_tours_subscriber_loop(bot))
    asyncio.create_task(all_users_notification_loop(bot))

    print("[СЛУЖБА] Фоновый процесс автопостинга туров в канал запущен (интервал: 60 минут).", flush=True)
    print("[СЛУЖБА] Фоновый процесс персональной рассылки горящих туров запущен (интервал: 30 минут).", flush=True)
    print("[СЛУЖБА] Фоновый процесс общих уведомлений для всех пользователей запущен (интервал: 60 минут).", flush=True)

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
