GS = chr(29)        # GS1 group separator (ASCII 29)
FNC1_CHAR = chr(232) # FNC1 symbol (ASCII 232)

class GS1Error(Exception):
    pass

def parse_gs1(raw: str, strict: bool = True) -> dict:
    if not raw:
        raise GS1Error("Пустой код")

    data = raw
    has_fnc1_start = False

    # 1. Поиск FNC1 в начале
    for prefix in ["]d2", "]d1", "]E0"]:
        if data.startswith(prefix):
            has_fnc1_start = True
            data = data[len(prefix):]
            break

    if not has_fnc1_start:
        if data.startswith(GS) or data.startswith(FNC1_CHAR):
            has_fnc1_start = True
            data = data[1:]

    # Если строгая проверка включена и FNC1 не найден
    if strict and not has_fnc1_start:
        raise GS1Error("Нарушение структуры GS1: Отсутствует символ FNC1 в начале кода. Настройте сканер или отключите проверку в настройках.")

    # 2. Проверка AI 01
    if not data.startswith("01"):
        # Если не начинается с 01, возможно FNC1 был в середине (ошибка сканера)
        # Но для Честного Знака 01 должен быть первым AI
        if strict:
            raise GS1Error("Нарушение структуры GS1: Код должен начинаться с '01' (GTIN)")

    # Пытаемся найти 01 если оно не в начале (для нестрогого режима)
    if not data.startswith("01"):
        idx_01 = data.find("01")
        if idx_01 != -1:
            data = data[idx_01:]
        else:
            raise GS1Error("Идентификатор AI 01 не найден")

    if len(data) < 16:
        raise GS1Error("Код слишком короткий")

    gtin = data[2:16]
    rest = data[16:]

    # 3. AI 21
    if not rest.startswith("21"):
        if strict:
            raise GS1Error("Нарушение структуры: ожидался идентификатор '21' (серийный номер)")
        idx_21 = rest.find("21")
        if idx_21 != -1:
            rest = rest[idx_21:]
        else:
            raise GS1Error("Идентификатор AI 21 не найден")

    rest = rest[2:]

    # 4. Поиск разделителя GS перед AI 93
    # Проверяем ASCII 29, ASCII 232 и ПРОБЕЛ (частое поведение сканеров)
    gs_idx = -1
    for sep in [GS, FNC1_CHAR, " "]:
        idx = rest.find(sep)
        if idx != -1:
            gs_idx = idx
            break

    if gs_idx != -1:
        serial = rest[:gs_idx]
        tail_part = rest[gs_idx+1:]
        # Удаляем AI 93 если он там есть
        if tail_part.startswith("93"):
            tail = tail_part[2:]
        else:
            tail = tail_part
    else:
        # Если разделителя нет, но есть 93
        if "93" in rest:
            if strict:
                raise GS1Error("Нарушение структуры GS1: Отсутствует разделитель GS перед AI 93")
            idx_93 = rest.find("93")
            serial = rest[:idx_93]
            tail = rest[idx_93+2:]
        else:
            # Нет ни разделителя, ни 93
            if strict:
                raise GS1Error("Нарушение структуры GS1: Отсутствует проверочный код (AI 93)")
            serial = rest
            tail = ""

    if not serial:
        raise GS1Error("Серийный номер пуст")

    clean = f"01{gtin}21{serial}"

    return {
        "gtin": gtin,
        "serial": serial,
        "clean": clean,
        "raw": raw
    }
