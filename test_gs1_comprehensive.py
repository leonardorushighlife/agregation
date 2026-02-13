import sys
from gs1 import parse_gs1, GS1Error

def test_code(code, strict=True):
    try:
        p = parse_gs1(code, strict=strict)
        print(f"SUCCESS: '{code.replace(chr(29), '<GS>')}' -> {p['clean']}")
    except GS1Error as e:
        print(f"ERROR: '{code.replace(chr(29), '<GS>')}' -> {e}")
    except Exception as e:
        print(f"EXCEPTION: '{code.replace(chr(29), '<GS>')}' -> {type(e).__name__}: {e}")

if __name__ == "__main__":
    strict_val = True
    if len(sys.argv) > 1 and sys.argv[1].lower() == "false":
        strict_val = False

    codes = [
        "0105449000000996215!!:SI(4pQb7Q93C5ie",
        "(01)05449000000996(21)5!!:SI(4pQb7Q(93)C5ie",
        "]d20105449000000996215!!:SI(4pQb7Q93C5ie",
        chr(232) + "0105449000000996215!!:SI(4pQb7Q93C5ie",
        chr(29) + "0105449000000996215!!:SI(4pQb7Q93C5ie",
        "GS0105449000000996215!!:SI(4pQb7Q93C5ie",
        "FNC10105449000000996215!!:SI(4pQb7Q93C5ie",
        "   0105449000000996215!!:SI(4pQb7Q93C5ie",
        "\x01\x020105449000000996215!!:SI(4pQb7Q93C5ie",
    ]

    for c in codes:
        test_code(c, strict=strict_val)
