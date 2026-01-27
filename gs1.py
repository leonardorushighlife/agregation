GS = chr(29)        # GS1 group separator
FNC1 = chr(232)     # FNC1 symbol

class GS1Error(Exception):
    pass

def parse_gs1(raw: str) -> dict:
    if not raw:
        raise GS1Error("Пустой код")

    # 1. Проверка на запрещенные текстовые вставки
    if raw.startswith("FNC1") or raw.startswith("GS"):
        raise GS1Error("Нарушение структуры GS1 DataMatrix (текстовое FNC1/GS)")

    # 2. Проверка на запрещенный первый символ GS
    if raw.startswith(GS):
        raise GS1Error("Нарушение структуры GS1 DataMatrix (первым символом GS)")

    # 3. Очистка от технических префиксов сканера
    data = raw
    if data.startswith("]d2"):
        data = data[3:]

    while data and ord(data[0]) < 32 and data[0] not in (FNC1, GS):
        data = data[1:]

    if data.startswith(FNC1):
        data = data[1:]

    # 4. Логическая проверка FNC1 по структуре
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

    # 6. Обработка серийного номера и криптохвоста
    # Пользователь указал, что GS может отсутствовать, так как это невидимый знак.
    # Если GS есть, делим по нему.
    if GS in rest:
        serial, tail = rest.split(GS, 1)
    else:
        # Если GS нет, ищем AI 93 как начало криптохвоста.
        # По стандарту ЧЗ серийный номер обычно имеет фиксированную длину для определенных групп,
        # но в общем случае он переменный.
        # Если мы видим '93' в остатке, предполагаем, что это начало хвоста.
        # ВАЖНО: AI 93 обычно идет после серийного номера.
        idx_93 = rest.find("93")
        if idx_93 != -1:
            serial = rest[:idx_93]
            tail = rest[idx_93:]
        else:
            serial = rest
            tail = ""

    if not serial:
        raise GS1Error("Пустой серийный номер")

    # Итоговый код для агрегации: 01 + GTIN + 21 + Serial (без криптохвоста)
    clean = f"01{gtin}21{serial}"

    return {
        "gtin": gtin,
        "serial": serial,
        "clean": clean,
        "raw": raw
    }
