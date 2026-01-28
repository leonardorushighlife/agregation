GS = chr(29)        # GS1 group separator (ASCII 29)
FNC1_CHAR = chr(232) # FNC1 symbol (ASCII 232, some scanners use this)

class GS1Error(Exception):
    pass

def parse_gs1(raw: str) -> dict:
    if not raw:
        raise GS1Error("Пустой код")

    # 1. Определение наличия FNC1 в начале
    # Проверяем AIM-префиксы и спецсимволы
    has_fnc1_start = False
    data = raw

    # AIM префиксы (]d2 - DataMatrix с FNC1)
    for prefix in ["]d2", "]d1", "]E0"]:
        if data.startswith(prefix):
            has_fnc1_start = True
            data = data[len(prefix):]
            break

    # Проверка на спецсимволы ASCII 29 или 232 в начале
    if not has_fnc1_start:
        if data.startswith(GS) or data.startswith(FNC1_CHAR):
            has_fnc1_start = True
            data = data[1:]

    if not has_fnc1_start:
        # Если сканер не прислал FNC1/префикс, это нарушение структуры для Честного Знака
        raise GS1Error("Нарушение структуры GS1: Отсутствует символ FNC1 в начале кода. Настройте сканер!")

    # 2. Проверка на AI 01 (GTIN)
    if not data.startswith("01"):
        raise GS1Error("Нарушение структуры GS1: Код после FNC1 должен начинаться с '01' (GTIN)")

    if len(data) < 16:
        raise GS1Error("Код слишком короткий для формата GS1")

    gtin = data[2:16]
    if not gtin.isdigit() or len(gtin) != 14:
        raise GS1Error("Неверный формат GTIN (ожидалось 14 цифр)")

    rest = data[16:]

    # 3. Проверка на AI 21 (Серийный номер)
    if not rest.startswith("21"):
        raise GS1Error("Нарушение структуры: ожидался идентификатор '21' (серийный номер)")

    rest = rest[2:]

    # 4. Поиск разделителя GS перед AI 93 (Криптохвост)
    # По стандарту GS1, после поля переменной длины (AI 21) должен идти GS (ASCII 29)
    # если за ним следует другой AI.

    gs_idx = rest.find(GS)
    if gs_idx == -1:
        # Также проверяем символ 232 как возможный разделитель
        gs_idx = rest.find(FNC1_CHAR)

    if gs_idx != -1:
        serial = rest[:gs_idx]
        tail_part = rest[gs_idx+1:]
        # Проверяем, что хвост начинается с 93 (необязательно, но желательно для ЧЗ)
        if not tail_part.startswith("93"):
            # Если там не 93, это все равно хвост
            pass
    else:
        # Если явного разделителя нет, проверяем, нет ли склеенного 93
        if "93" in rest:
            raise GS1Error("Нарушение структуры GS1: Отсутствует разделитель GS перед проверочным кодом (AI 93)")
        else:
            # Код без криптохвоста? В ЧЗ это ошибка структуры.
            raise GS1Error("Нарушение структуры GS1: Отсутствует проверочный код (криптохвост)")

    if not serial:
        raise GS1Error("Серийный номер не может быть пустым")

    # Для агрегации и отчетов используем 01 + GTIN + 21 + Serial
    clean = f"01{gtin}21{serial}"

    return {
        "gtin": gtin,
        "serial": serial,
        "clean": clean,
        "raw": raw # Полный исходный код для проверки дубликатов
    }
