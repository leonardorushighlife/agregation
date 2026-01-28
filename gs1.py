GS = chr(29)        # GS1 group separator (ASCII 29)
FNC1_CHAR = chr(232) # FNC1 symbol (ASCII 232, some scanners use this)

class GS1Error(Exception):
    pass

def parse_gs1(raw: str) -> dict:
    if not raw:
        raise GS1Error("Пустой код")

    # 1. Проверка наличия FNC1 в начале (структурная)
    # По стандарту GS1 DataMatrix должен начинаться с символа FNC1.
    # Сканеры передают его как ASCII 29, либо через AIM-префикс ]d2.

    has_fnc1_start = False
    data = raw

    # Проверка AIM префиксов
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
        raise GS1Error("Нарушение структуры GS1: Отсутствует FNC1 в начале кода")

    # 2. Логическая проверка начала данных (01 GTIN)
    if not data.startswith("01"):
        raise GS1Error("Нарушение структуры GS1: Код должен начинаться с AI 01 (GTIN)")

    if len(data) < 16:
        raise GS1Error("Код слишком короткий")

    gtin = data[2:16]
    if not gtin.isdigit() or len(gtin) != 14:
        raise GS1Error("Неверный формат GTIN (должно быть 14 цифр)")

    rest = data[16:]

    # 3. AI (21) Серийный номер
    if not rest.startswith("21"):
        raise GS1Error("Нарушение структуры: ожидался AI 21 (серийный номер) после GTIN")

    rest = rest[2:]

    # 4. Проверка разделителя GS перед криптохвостом (AI 93)
    # Т.к. AI 21 имеет переменную длину, перед следующим AI обязан быть GS

    serial = ""
    tail = ""

    gs_idx = rest.find(GS)
    if gs_idx != -1:
        serial = rest[:gs_idx]
        tail_part = rest[gs_idx+1:]
        if not tail_part.startswith("93"):
            # По стандарту может быть другой AI, но в Честном Знаке обычно 93
            # Если там не 93, мы все равно считаем это хвостом для очистки
            tail = tail_part
        else:
            tail = tail_part[2:] # Удаляем '93'
    else:
        # Если GS нет, проверяем, есть ли 93.
        # Если есть 93 без GS - это нарушение структуры для переменного поля 21.
        if "93" in rest:
            raise GS1Error("Нарушение структуры GS1: Отсутствует разделитель GS перед AI 93")
        else:
            # Если нет ни GS, ни 93, возможно это код без криптохвоста (редко)
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
