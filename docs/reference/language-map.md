# Language map formats

Transpilation produces a bidirectional map between the `.ldpy` source and the
generated Python. Two serialisations exist.

## JSON v1 (native, richer)

Written as `module.ldpy.map` by `ldpy.build`; the working format of the
language server and the debugger tooling.

```text
{ "version": 1, "source": "module.ldpy", "generated": ".ldpy-build/module.py",
  "segments": [
    {"kind": "synthetic",    "gen": [0,0,0,67]},
    {"kind": "island:prefix","src": [0,0,0,25],  "gen": [1,0,1,52]},
    {"kind": "copy",         "src": [0,25,1,5],  "gen": [1,52,2,5]} ] }
```

- Positions are `[line0, col0, line1, col1]`, 0-based, end-exclusive.
- `copy` — text reproduced verbatim; position translation inside is exact.
- `island:KIND` — an island (`prefix`, `base`, `iri`, `pname`, `literal`,
  `var`, `firi`, `fnode`, `graph`) mapped at region granularity.
- `synthetic` — generated text with no source (the runtime prelude).

## Source Map v3 (standard)

Written as `module.py.map`; ECMA-426, base64-VLQ `mappings`, for tools of
the JavaScript lineage. One mapping point per copied line plus one per island
start. Produced by `LanguageMap.to_sourcemap_v3()`.

```python
from ldpy.transpiler import transpile
sm = transpile("x = <http://e/a>\n", "m.ldpy").map.to_sourcemap_v3()
assert sm["version"] == 3 and sm["sources"] == ["m.ldpy"]
```
