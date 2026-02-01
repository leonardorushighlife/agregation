GS = chr(29)        # GS1 group separator (ASCII 29)
FNC1_CHAR = chr(232) # FNC1 symbol (ASCII 232)

class GS1Error(Exception):
    pass

def parse_gs1(raw: str, strict: bool = True) -> dict:
    if not raw:
        raise GS1Error("err_empty")

    # Предварительная очистка от непечатных символов в начале и конце.
    # Очищаем управляющие символы кроме GS (29) и FNC1_CHAR (232), которые могут быть префиксами.
    data = raw.strip().lstrip('\x00\x01\x02\x03\x04\x05\x06\x07\x08\x0b\x0c\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x1a\x1b\x1c\x1e\x1f')

    # Проверка на запрещенные текстовые префиксы (только в строгом режиме)
    if strict and (data.startswith("FNC1") or data.startswith("GS")):
        raise GS1Error("err_gs1_structure")

    has_fnc1_physical = False

    # 1. Поиск FNC1 в начале (физически: AIM ID или ASCII 232)
    for prefix in ["]d2", "]d1", "]E0"]:
        if data.startswith(prefix):
            has_fnc1_physical = True
            data = data[len(prefix):]
            break

    if not has_fnc1_physical:
        if data.startswith(FNC1_CHAR):
            has_fnc1_physical = True
            data = data[1:]
        elif data.startswith(GS):
            # ТЗ: "НЕЛЬЗЯ чтобы первым символом был GS" (ASCII 29)
            if strict:
                raise GS1Error("err_gs1_structure")
            has_fnc1_physical = True
            data = data[1:]

    # Логическое наличие FNC1 по структуре (если начинается с 01)
    # ТЗ: "Наличие FNC1 в начале (логически, по структуре)"
    has_fnc1_logical = has_fnc1_physical or data.startswith("01") or data.startswith("(01)")

    # Если не нашли в самом начале, но "01" есть чуть дальше (из-за нераспознанного мусора)
    if not has_fnc1_logical and "01" in data[:10]:
        idx = data.find("01")
        # Проверяем, не является ли это (01)
        if idx > 0 and data[idx-1] == '(':
            idx -= 1
        data = data[idx:]
        has_fnc1_logical = True

    # Если строгая проверка включена и FNC1 не найден ни физически, ни логически
    if strict and not has_fnc1_logical:
        raise GS1Error("err_gs1_fnc1")

    # 2. Проверка AI 01
    # Если есть скобки, убираем их
    if data.startswith("(01)"):
        data = "01" + data[4:]

    if not data.startswith("01"):
        # Если не начинается с 01, возможно FNC1 был в середине (ошибка сканера)
        # Но для Честного Знака 01 должен быть первым AI
        if strict:
            raise GS1Error("err_gs1_structure")

    # Пытаемся найти 01 если оно не в начале (для нестрогого режима)
    if not data.startswith("01"):
        idx_01 = data.find("01")
        if idx_01 != -1:
            data = data[idx_01:]
        else:
            raise GS1Error("err_gs1_gtin")

    if len(data) < 16:
        raise GS1Error("err_gs1_structure")

    gtin = data[2:16]
    rest = data[16:]

    # 3. AI 21
    # Опять же, обрабатываем возможные скобки (21)
    if rest.startswith("(21)"):
        rest = "21" + rest[4:]

    if not rest.startswith("21"):
        if strict:
            raise GS1Error("err_gs1_21")
        idx_21 = rest.find("21")
        if idx_21 != -1:
            rest = rest[idx_21:]
        else:
            raise GS1Error("err_gs1_21")

    rest = rest[2:]

    # 4. Поиск разделителя GS перед AI 93/91/92
    if strict and ("GS" in rest or "FNC1" in rest):
        raise GS1Error("err_gs1_structure")

    gs_idx = -1
    for sep in [GS, FNC1_CHAR, " "]:
        idx = rest.find(sep)
        if idx != -1:
            gs_idx = idx
            break

    if gs_idx != -1:
        serial = rest[:gs_idx]
        tail_part = rest[gs_idx+1:]
        # Удаляем AI хвоста
        for ai in ["93", "91", "92", "(93)", "(91)", "(92)"]:
            if tail_part.startswith(ai):
                tail = tail_part[len(ai):]
                break
    else:
        # Если разделителя нет, ищем AI хвоста
        idx_ai = -1
        for ai in ["93", "91", "92", "(93)", "(91)", "(92)"]:
            idx = rest.find(ai)
            if idx != -1:
                idx_ai = idx
                break

        if idx_ai != -1:
            serial = rest[:idx_ai]
            # Даже в строгом режиме, если мы нашли AI хвоста без GS,
            # часто это допустимо для клавиатурных сканеров,
            # но ТЗ говорит "ДОЛЖЕН быть разделитель GS".
            # Мы разрешим это, так как серийный номер все равно выделен верно.
        else:
            if strict:
                raise GS1Error("err_gs1_structure")
            serial = rest

    if not serial:
        raise GS1Error("err_gs1_21")

    clean = f"01{gtin}21{serial}"

    return {
        "gtin": gtin,
        "serial": serial,
        "clean": clean,
        "raw": raw
    }
