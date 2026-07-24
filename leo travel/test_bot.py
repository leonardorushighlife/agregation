import asyncio
import os
import unittest
from unittest.mock import patch, MagicMock

# Импортируем функции из bot.py
from bot import generate_referral_link, save_channel_id, load_channel_id, fetch_cheapest_tours, analyze_tour_with_gigachat, CONFIG_FILE


class TestLeoTravelBot(unittest.TestCase):
    def setUp(self):
        # Очищаем файл конфигурации перед тестом
        if os.path.exists(CONFIG_FILE):
            os.remove(CONFIG_FILE)

    def tearDown(self):
        # Удаляем файл конфигурации после теста
        if os.path.exists(CONFIG_FILE):
            os.remove(CONFIG_FILE)

    def test_generate_referral_link_default(self):
        # Проверяем генерацию ссылки без партнерского маркера
        link = generate_referral_link("12345", partner_id="ВАШ_PARTNER_ID")
        self.assertEqual(link, "https://level.travel/hotels/12345")

    def test_generate_referral_link_with_partner(self):
        # Проверяем генерацию реферальной ссылки со специальным маркером
        link = generate_referral_link("12345", partner_id="777999")
        self.assertEqual(link, "https://level.travel/hotels/12345?tp_marker=777999")

    def test_channel_id_persistence(self):
        # Проверяем сохранение и чтение ID канала
        test_channel = "@my_best_tours_channel"
        save_channel_id(test_channel)

        loaded = load_channel_id()
        self.assertEqual(loaded, test_channel)

    def test_fetch_cheapest_tours_demo(self):
        # Запускаем асинхронный тест в цикле событий
        loop = asyncio.get_event_loop()
        tours = loop.run_until_complete(
            fetch_cheapest_tours(country="Турция", stars=4)
        )

        # Проверяем, что вернулся список предложений
        self.assertIsInstance(tours, list)
        self.assertGreater(len(tours), 0)

        # Проверяем структуру возвращаемых данных
        first_tour = tours[0]
        self.assertIn("hotel", first_tour)
        self.assertIn("price", first_tour)
        self.assertIn("price_double", first_tour)
        self.assertIn("hotel_id", first_tour)
        self.assertEqual(first_tour["stars"], 4)

    def test_analyze_tour_offline(self):
        # Проверяем работу оффлайн-анализатора на русском языке
        loop = asyncio.get_event_loop()
        analysis = loop.run_until_complete(
            analyze_tour_with_gigachat(
                hotel="Rixos Premium Tekirova",
                resort="Турция, Кемер",
                price=150000,
                nights=7,
                stars=5
            )
        )

        self.assertIsInstance(analysis, str)
        # Убеждаемся, что возвращается корректный содержательный русский текст
        self.assertTrue("Анализ" in analysis or "тур" in analysis or "цена" in analysis)


if __name__ == "__main__":
    unittest.main()
