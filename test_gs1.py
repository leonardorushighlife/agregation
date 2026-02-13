from gs1 import parse_gs1

codes = [
    "0105449000000996215!!:SI(4pQb7Q93C5ie",
    "0104650065313835215tY3f'\\x1d93cXhE",
]

for c in codes:
    try:
        p = parse_gs1(c, strict=True)
        print(f"OK: {c} -> {p['clean']}")
    except Exception as e:
        print(f"ERROR: {c} -> {e}")
