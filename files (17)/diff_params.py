import json, sys, math
a, b = (json.load(open(p)) for p in sys.argv[1:3])
pa, pb = a["params"], b["params"]
print(f"A = pybamm {a['pybamm']} ({len(pa)} params)   B = pybamm {b['pybamm']} ({len(pb)} params)")
only_a = sorted(set(pa) - set(pb)); only_b = sorted(set(pb) - set(pa))
print(f"\nonly in A ({len(only_a)}):"); [print("  ", k) for k in only_a]
print(f"\nonly in B ({len(only_b)}):"); [print("  ", k) for k in only_b]
print("\nvalue differences (rel > 1e-9, or function name differs):")
n = 0
for k in sorted(set(pa) & set(pb)):
    x, y = pa[k], pb[k]
    if isinstance(x, float) and isinstance(y, float):
        if not math.isclose(x, y, rel_tol=1e-9, abs_tol=0): print(f"   {k}: {x:g} -> {y:g}"); n += 1
    elif x != y: print(f"   {k}: {x} -> {y}"); n += 1
print(f"\n{n} differing values")
