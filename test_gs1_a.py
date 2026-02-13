from gs1 import parse_gs1
try:
    res = parse_gs1("A0105449000000996215!!:SI(4pQb7Q93C5ie", strict=True)
    print(f"SUCCESS: {res['clean']}")
except Exception as e:
    print(f"ERROR: {e}")
