#!/bin/sh
# Measure the size and alignment of every struct in scripts/abi-sizes.txt and the offset of every
# field in scripts/abi-offsets.txt with the host C compiler and compare. The expected values come from the bindgen IR through
# scripts/gen_bindings.py; this probe proves the IR matches the real compiler.
#
# Usage:
#   scripts/probe-layout.sh    fail if any measured layout differs from scripts/abi-*.txt
#
# The compiler is cc under a Linux shell and cl under a Windows one, so each CI job measures
# its own platform against the same file.
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HEADER="$ROOT/vendor/ufbx/ufbx.h"
SIZES="$ROOT/scripts/abi-sizes.txt"
OFFSETS="$ROOT/scripts/abi-offsets.txt"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

if [ ! -f "$HEADER" ]; then
    echo "ERROR: vendor/ufbx is empty. Run: git submodule update --init" >&2
    exit 1
fi

case "$(uname -s)" in
    MINGW*|MSYS*|CYGWIN*) INCLUDE_PATH="$(cygpath -m "$HEADER")" ;;
    *)                    INCLUDE_PATH="$HEADER" ;;
esac

{
    echo '#include <stdio.h>'
    echo '#include <stddef.h>'
    echo "#include \"$INCLUDE_PATH\""
    echo 'int main(void) {'
    while read -r cname size align; do
        [ -z "$cname" ] && continue
        printf '    printf("%s %%zu %%zu\\n", sizeof(%s), _Alignof(%s));\n' "$cname" "$cname" "$cname"
    done < "$SIZES"
    while read -r cname field offset; do
        [ -z "$cname" ] && continue
        printf '    printf("%s %s %%zu\\n", offsetof(%s, %s));\n' "$cname" "$field" "$cname" "$field"
    done < "$OFFSETS"
    echo '    return 0;'
    echo '}'
} > "$WORK/probe.c"

case "$(uname -s)" in
    MINGW*|MSYS*|CYGWIN*)
        (cd "$WORK" && MSYS2_ARG_CONV_EXCL="*" cl -nologo -std:c11 -Fe:probe.exe probe.c)
        PROBE="$WORK/probe.exe"
        ;;
    *)
        cc -std=c11 -o "$WORK/probe" "$WORK/probe.c"
        PROBE="$WORK/probe"
        ;;
esac

"$PROBE" | tr -d "\r" > "$WORK/sizes.txt"

cat "$SIZES" "$OFFSETS" > "$WORK/expected.txt"
if ! diff -u "$WORK/expected.txt" "$WORK/sizes.txt"; then
    echo "ERROR: measured layout differs from scripts/abi-*.txt" >&2
    exit 1
fi
echo "layout matches the C compiler"
