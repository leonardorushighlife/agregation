"""
Скрипт для сборки Telegram-бота "Leo Travel" в один клик.

Инструкция:
1. Установите PyInstaller и aiogram:
   pip install pyinstaller aiogram aiohttp
2. Запустите данный скрипт:
   python build_exe.py
3. Готовый exe-файл появится в папке 'dist'.
"""

import os
import subprocess
import sys


def main():
    print("=== Подготовка к сборке Telegram-бота Leo Travel ===")

    try:
        import PyInstaller
    except ImportError:
        print("Библиотека PyInstaller не найдена. Устанавливаем...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    try:
        import aiogram
    except ImportError:
        print("Библиотека aiogram не найдена. Устанавливаем...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "aiogram"])

    print("Запуск сборки с помощью PyInstaller...")

    # Опции сборки:
    # --onefile : собрать в один файл
    # --noconsole : скрыть черное окно консоли при запуске (если необходимо, уберите этот флаг для отладки)
    cmd = [
        "pyinstaller",
        "--onefile",
        "bot.py"
    ]

    try:
        subprocess.check_call(cmd)
        print("\n==============================================")
        print(" Сборка успешно завершена!")
        print(" Исполняемый файл находится в папке: dist/bot")
        print("==============================================")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Произошла ошибка во время сборки: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
