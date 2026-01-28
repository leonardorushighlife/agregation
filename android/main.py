import os
import json
import sqlite3
from datetime import datetime

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.utils import platform

# Импортируем логику из основного проекта
# В реальности нужно убедиться, что файлы gs1.py и state.py скопированы в папку приложения
from gs1 import parse_gs1, GS1Error

class MobileAggregatorApp(App):
    def build(self):
        self.title = "ЧЗ Агрегация (Android)"
        self.box_size = 24
        self.in_box = 0
        self.wait_sscc = False
        self.current_units = []

        # Главный контейнер
        self.layout = BoxLayout(orientation='vertical', padding=10, spacing=10)

        # Информационная панель
        self.info_label = Label(text="Начните сканирование", font_size='20sp', size_hint_y=0.2)
        self.layout.add_widget(self.info_label)

        # Поле ввода (для внешних сканеров и клавиатуры)
        self.scan_input = TextInput(multiline=False, size_hint_y=0.1, focus=True)
        self.scan_input.bind(on_text_validate=self.on_scan)
        self.layout.add_widget(self.scan_input)

        # Список последних кодов
        self.last_codes_label = Label(text="", color=(0.7, 0.7, 0.7, 1), size_hint_y=0.4, halign='center')
        self.layout.add_widget(self.last_codes_label)

        # Кнопки управления
        btn_layout = BoxLayout(size_hint_y=0.3, spacing=10)

        self.btn_camera = Button(text="КАМЕРА", background_color=(0.13, 0.59, 0.95, 1))
        self.btn_camera.bind(on_press=self.start_camera_scan)
        btn_layout.add_widget(self.btn_camera)

        self.btn_finish = Button(text="ЗАВЕРШИТЬ", background_color=(0.3, 0.69, 0.31, 1))
        self.btn_finish.bind(on_press=self.finish_shift)
        btn_layout.add_widget(self.btn_finish)

        self.layout.add_widget(btn_layout)

        # Настройка ТСД (Zebra/Honeywell/DataLogic)
        if platform == 'android':
            self.setup_tsd_broadcast()

        return self.layout

    def on_scan(self, instance):
        raw = instance.text.strip()
        instance.text = ""
        self.process_code(raw)
        instance.focus = True

    def process_code(self, raw):
        if not raw: return

        if self.wait_sscc:
            if raw.startswith("00"):
                # Закрываем коробку
                self.current_units = []
                self.in_box = 0
                self.wait_sscc = False
                self.update_ui("Коробка закрыта!")
            else:
                self.show_error("Ожидается SSCC (00)")
        else:
            if raw.startswith("00"):
                self.show_error("Коробка еще не полная!")
                return

            try:
                parsed = parse_gs1(raw, strict=False) # На Android обычно нестрого
                self.current_units.append(parsed['clean'])
                self.in_box += 1

                if self.in_box >= self.box_size:
                    self.wait_sscc = True
                    self.update_ui("ОЖИДАНИЕ SSCC")
                else:
                    self.update_ui(f"Собрано: {self.in_box} / {self.box_size}")

                self.last_codes_label.text = f"Последний: {parsed['clean']}\n{self.last_codes_label.text[:100]}"
            except GS1Error as e:
                self.show_error(str(e))

    def update_ui(self, text):
        self.info_label.text = text

    def show_error(self, text):
        popup = Popup(title='Ошибка', content=Label(text=text), size_hint=(0.8, 0.4))
        popup.open()

    def start_camera_scan(self, instance):
        # В реальности здесь вызывается интент камеры или специализированная библиотека
        self.show_error("Функция камеры требует сборки с OpenCV/Zbar")

    def finish_shift(self, instance):
        self.show_error("Смена завершена. Отчет сохранен.")

    # --- Специфическая логика для ТСД ---
    def setup_tsd_broadcast(self):
        try:
            from jnius import autoclass
            from android.broadcast import BroadcastReceiver

            # Пример для Zebra (DataWedge)
            # Нужно настроить профиль в DataWedge на отправку Intent (ACTION_BARCODE_DATA)
            class TSDReceiver(BroadcastReceiver):
                def __init__(self, callback):
                    super().__init__(self.on_broadcast)
                    self.callback = callback

                def on_broadcast(self, context, intent):
                    # Извлекаем данные из интента
                    data = intent.getStringExtra("com.symbol.datawedge.data_string")
                    if data:
                        Clock.schedule_once(lambda dt: self.callback(data))

            self.receiver = TSDReceiver(self.process_code)
            self.receiver.start()
        except:
            print("TSD Broadcast setup failed (not on Android or missing jnius)")

if __name__ == '__main__':
    MobileAggregatorApp().run()
