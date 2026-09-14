# Smoke test

`c3c test` from this directory compiles the binding through `libs/ufbx.c3l`, a symlink to the
repository root, and runs `src/smoke.c3` against `vendor/ufbx/data/maya_cube_7400_binary.fbx`
from the upstream submodule: a Maya 1 cm cube with one material and one empty take.
