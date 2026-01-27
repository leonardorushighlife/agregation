GS = chr(29)        # GS1 group separator
FNC1 = chr(232)     # FNC1 symbol

class GS1Error(Exception):
    pass

def parse_gs1(raw: str) -> dict:
    if not raw:
        raise GS1Error("Пустой код")

    # 1. Проверка на запрещенные текстовые вставки
    if "FNC1" in raw or "GS" in raw:
        if raw.startswith("FNC1") or raw.startswith("GS") or "GS" in raw:
             raise GS1Error("Нарушение структуры GS1 DataMatrix (текстовое FNC1/GS)")

    # 2. Проверка на запрещенный первый символ GS
    if raw.startswith(GS):
        raise GS1Error("Нарушение структуры GS1 DataMatrix (первым символом GS)")

    # 3. Очистка от технических префиксов сканера и невидимых символов
    data = raw

    # Распространенные префиксы GS1
    for prefix in ["]d2", "]d1", "]E0"]:
        if data.startswith(prefix):
            data = data[len(prefix):]

    # Удаляем все управляющие символы и FNC1 с начала строки
    while data and (ord(data[0]) < 32 or ord(data[0]) == 232 or data[0] == FNC1):
        data = data[1:]

    # 4. Логическая проверка FNC1 по структуре
    if not data.startswith("01"):
        raise GS1Error("Нарушение структуры GS1 DataMatrix (отсутствует логический FNC1/01)")

    # AI (01) GTIN — 14 цифр
    if len(data) < 16:
        raise GS1Error("Код слишком короткий")

    gtin = data[2:16]
    if not gtin.isdigit() or len(gtin) != 14:
        raise GS1Error("Неверный формат GTIN")

    rest = data[16:]

    # 5. AI (21) Серийный номер
    if not rest.startswith("21"):
        raise GS1Error("Нарушение структуры GS1 DataMatrix (ожидался AI 21 после GTIN)")

    rest = rest[2:]

    # 6. Обработка серийного номера и криптохвоста
    if GS in rest:
        serial, tail = rest.split(GS, 1)
    else:
        # Ищем AI 93 как начало криптохвоста
        idx_93 = rest.find("93")
        if idx_93 != -1:
            serial = rest[:idx_93]
            tail = rest[idx_93:]
        else:
            serial = rest
            tail = ""

    if not serial:
        raise GS1Error("Пустой серийный номер")

    # Итоговый код для агрегации: 01 + GTIN + 21 + Serial
    clean = f"01{gtin}21{serial}"

    return {
        "gtin": gtin,
        "serial": serial,
        "clean": clean,
        "raw": raw
    }
