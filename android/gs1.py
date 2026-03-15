GS = chr(29)        # GS1 group separator (ASCII 29)
FNC1_CHAR = chr(232) # FNC1 symbol (ASCII 232)

class GS1Error(Exception):
    pass

def parse_gs1(raw: str, strict: bool = True) -> dict:
    if not raw:
        raise GS1Error("err_empty")

    data = raw.strip()

    if strict and (data.startswith("FNC1") or data.startswith("GS")):
        raise GS1Error("err_gs1_structure")

    has_fnc1_physical = False

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
            if strict:
                raise GS1Error("err_gs1_structure")
            has_fnc1_physical = True
            data = data[1:]

    has_fnc1_logical = has_fnc1_physical or data.startswith("01") or data.startswith("(01)")

    if strict and not has_fnc1_logical:
        raise GS1Error("err_gs1_fnc1")

    if data.startswith("(01)"):
        data = "01" + data[4:]

    if not data.startswith("01"):
        if strict:
            raise GS1Error("err_gs1_structure")

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
        if tail_part.startswith("93"):
            tail = tail_part[2:]
        elif tail_part.startswith("(93)"):
            tail = tail_part[4:]
        else:
            tail = tail_part
    else:
        if "93" in rest or "(93)" in rest:
            idx_93 = rest.find("93")
            if idx_93 == -1: idx_93 = rest.find("(93)")
            if strict:
                raise GS1Error("err_gs1_structure")
            serial = rest[:idx_93]
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
