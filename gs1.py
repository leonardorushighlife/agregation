GS = chr(29)        # GS1 group separator
FNC1 = chr(232)     # FNC1 symbol

class GS1Error(Exception):
    pass

def parse_gs1(raw: str) -> dict:
    if not raw:
        raise GS1Error("Пустой код")

    # 1. Проверка на запрещенные текстовые вставки (по требованию промпта)
    if raw.startswith("FNC1") or raw.startswith("GS"):
        raise GS1Error("Нарушение структуры GS1 DataMatrix (текстовое FNC1/GS)")

    # 2. Проверка на запрещенный первый символ GS (по требованию промпта)
    if raw.startswith(GS):
        raise GS1Error("Нарушение структуры GS1 DataMatrix (первым символом GS)")

    # 3. Очистка от технических префиксов сканера
    data = raw

    # Удаляем идентификатор символики GS1 DataMatrix (часто ]d2)
    if data.startswith("]d2"):
        data = data[3:]

    # Удаляем непечатаемые символы в начале, которые могут быть префиксами
    while data and ord(data[0]) < 32 and data[0] not in (FNC1, GS):
        data = data[1:]

    # Обработка опционального символа FNC1 (\xe8)
    if data.startswith(FNC1):
        data = data[1:]

    # 4. Логическая проверка FNC1 по структуре (должно начинаться с AI 01)
    if not data.startswith("01"):
        raise GS1Error("Отсутствует FNC1 в начале GS1 DataMatrix")

    # AI (01) GTIN — 14 цифр
    gtin = data[2:16]
    if len(gtin) != 14 or not gtin.isdigit():
        raise GS1Error("Неверный формат GTIN")

    rest = data[16:]

    # 5. AI (21) Серийный номер
    if not rest.startswith("21"):
        raise GS1Error("Отсутствует AI (21) Серийный номер")

    rest = rest[2:]

    # 6. Проверка разделителя GS после (21) серийного номера
    # По стандарту GS нужен только если за переменным полем идет другое поле.
    if GS in rest:
        serial, tail = rest.split(GS, 1)
    else:
        # Если GS нет, но есть AI 93 (криптохвост), это ошибка структуры
        if len(rest) > 10 and "93" in rest[5:]:
            raise GS1Error("Нарушение структуры GS1 (отсутствует разделитель GS)")
        serial = rest
        tail = ""

    if not serial:
        raise GS1Error("Пустой серийный номер")

    # 7. AI (93) криптохвост — допускается по промпту
    if tail:
        if not tail.startswith("93"):
            raise GS1Error("Нарушена структура GS1 (неверный AI после серийного номера)")

    # Итоговый код для агрегации: 01 + GTIN + 21 + Serial
    clean = f"01{gtin}21{serial}"

    return {
        "gtin": gtin,
        "serial": serial,
        "clean": clean,
        "raw": raw
    }
