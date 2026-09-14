# ufbx.c3l

C3 bindings for [ufbx](https://github.com/ufbx/ufbx), a single-file FBX, OBJ and MTL loader
written in C. Module `ufbx`, package `ufbx`, C3 0.8.3.

The raw layer is generated. `scripts/gen_bindings.py` runs upstream's own bindgen
(`vendor/ufbx/bindgen`) and writes `src/ufbx.c3i` with every type, enum, constant, data global
and function of the header, and `src/layout.c3` with the size, alignment and field offsets of
every struct. `scripts/probe-layout.sh` measures the same layouts with the host C compiler, so
the generated pins are checked against a real compiler on both targets. `src/ufbx.c3` adds
faults for every `ufbx_error_type` and a few wrappers that take C3 slices and strings.

## Using it

Add the repository as a git submodule (recursive, for `vendor/ufbx`) into the directory your
project searches for libraries, then name `ufbx` as a dependency:

```json
{
  "dependency-search-paths": [ "lib" ],
  "dependencies": [ "ufbx" ]
}
```

`csrc/ufbx.c` compiles the ufbx implementation through the package's `c-sources` on
`linux-x64` and `windows-x64`; there is no native archive. The Windows target sets
`"wincrt": "static"`.

```c3
import std::io;
import ufbx;

fn void? show(String path) {
    ufbx::LoadOpts options = {
        .target_axes        = ufbx::axes_right_handed_y_up,
        .target_unit_meters = 1,
        .space_conversion   = ufbx::SpaceConversion.MODIFY_GEOMETRY,
    };
    ufbx::Scene* scene = ufbx::load_file(path, &options)!;
    defer ufbx::free_scene(scene);
    foreach (node : scene.nodes) {
        io::printfn("%s has %d children", node.name, node.children.len);
    }
}
```

Type mapping: `ufbx_real` is `double`, `ufbx_string` is `String`, `ufbx_blob` is `char[]`, every
`ufbx_*_list` is a slice of its element (`ufbx_node_list` is `Node*[]`), anonymous unions and
structs stay anonymous. Sequential enums are `enum Name : int`; flag enums and the enums with
explicit values are `typedef Name = int` with constants. A field named after a C3 keyword gets a
trailing underscore (`OpenFileCb.fn_`). The six `static inline` header functions have no linkable
symbol and are not declared.

Wrappers: `load_file`, `bake_anim`, `triangulate_face`, `generate_indices`. Their raw externs carry
the `_raw` suffix; every other function keeps its plain name (`free_scene`, `free_baked_anim`).
Faults: one per non-`NONE` `ufbx_error_type`, with the prefix stripped (`FILE_NOT_FOUND`, `IO`,
`UNRECOGNIZED_FILE_FORMAT`, ...).

## Development

```sh
python3 scripts/gen_bindings.py            # regenerate after a ufbx upgrade
python3 scripts/gen_bindings.py --check    # generated files match a fresh run
scripts/probe-layout.sh                    # layouts against the host C compiler
c3c compile-only --no-obj src/*.c3i src/*.c3 && rm -rf obj
cd test && c3c test                        # smoke test on upstream data/maya_cube_7400_binary.fbx
```

CI runs the generator check on `ubuntu-24.04`, and the probe, package compile and smoke test on
`ubuntu-24.04` and `windows-2022`.
