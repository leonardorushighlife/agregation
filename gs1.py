import re

GS = chr(29)        # GS1 group separator
FNC1_ALT = chr(232)  # FNC1 (может приходить от сканера)
FNC1_PHYS = chr(142) # FNC1 (в некоторых режимах сканера)

class GS1Error(Exception):
    pass

def parse_gs1(raw: str) -> dict:
    if not raw:
        raise GS1Error("Пустой код")

    # Очистка от мусора в начале (не-буквенно-цифровые, кроме спецсимволов GS1)
    data = re.sub(r'^[^\w\]\(\x1d\x8e]+', '', raw)

    # Распознавание FNC1
    fnc1_present = False
    if data.startswith(GS) or data.startswith(FNC1_ALT) or data.startswith(FNC1_PHYS):
        fnc1_present = True
        data = data[1:]
    elif data.startswith("]d2") or data.startswith("]d1"): # Префиксы DataMatrix
        fnc1_present = True
        data = data[3:]
    elif data.startswith("01") and len(data) >= 16:
        # Эвристика: если начинается с 01 и далее 14 цифр — скорее всего FNC1 был, но сканер его съел
        fnc1_present = True

    if not fnc1_present:
        raise GS1Error("Отсутствует FNC1 в начале GS1 DataMatrix")

    # 2. AI (01) GTIN — 14 цифр
    if not data.startswith("01"):
        raise GS1Error("Отсутствует AI (01) GTIN")

    gtin = data[2:16]
    if len(gtin) != 14 or not gtin.isdigit():
        raise GS1Error("Неверный формат GTIN")

    rest = data[16:]

    # 3. AI (21) серийный номер (переменной длины)
    if not rest.startswith("21"):
        raise GS1Error("Отсутствует AI (21) Серийный номер")

    rest = rest[2:]

    # Ищем разделитель для переменной длины
    if GS in rest:
        serial, tail = rest.split(GS, 1)
    elif FNC1_ALT in rest:
        serial, tail = rest.split(FNC1_ALT, 1)
    elif FNC1_PHYS in rest:
        serial, tail = rest.split(FNC1_PHYS, 1)
    else:
        # Если разделителей нет, пробуем найти AI (93)
        if "93" in rest:
            idx = rest.find("93")
            serial = rest[:idx]
            tail = rest[idx:]
        else:
            serial = rest
            tail = ""

    if not serial:
        raise GS1Error("Пустой серийный номер")

    # Очистка серийного номера от возможных остатков
    serial = serial.split('\x1d')[0].split('\x1e')[0]

    clean = f"01{gtin}21{serial}"

    return {
        "gtin": gtin,
        "serial": serial,
        "clean": clean,   # БЕЗ 93 — для XML / дубликатов / агрегации
        "raw": raw        # КАК ОТСКАНИРОВАЛИ — для CSV / ошибок
    }

def is_sscc(code: str) -> bool:
    """Проверка SSCC кода: должен начинаться с '00' и иметь 18-20 цифр"""
    # Убираем возможные скобки (00)
    clean = code.replace("(", "").replace(")", "")
    if clean.startswith("00") and len(clean) >= 18 and clean[2:].isdigit():
        return True
    return False
