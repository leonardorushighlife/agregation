GS = chr(29)        # GS1 group separator
FNC1 = chr(232)     # FNC1 (часто именно так приходит от сканера)


class GS1Error(Exception):
    pass


def parse_gs1(raw: str) -> dict:
    if not raw:
        raise GS1Error("Пустой код")

    # 1. FNC1 строго первым символом
    if raw[0] not in (FNC1, GS):
        raise GS1Error("Отсутствует FNC1 в начале GS1 DataMatrix")

    data = raw[1:]

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

    if GS in rest:
        serial, tail = rest.split(GS, 1)
    else:
        serial = rest
        tail = ""

    if not serial:
        raise GS1Error("Пустой серийный номер")

    # 4. AI (93) криптохвост — допускается
    if tail:
        if not tail.startswith("93"):
            raise GS1Error("Нарушена структура GS1 (лишние данные)")
        # криптохвост оставляем в raw, но не используем в clean

    clean = f"01{gtin}21{serial}"

    return {
        "gtin": gtin,
        "serial": serial,
        "clean": clean,   # БЕЗ 93 — для XML / дубликатов / агрегации
        "raw": raw        # КАК ОТСКАНИРОВАЛИ — для CSV / ошибок
    }
