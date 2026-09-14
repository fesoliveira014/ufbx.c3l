#!/usr/bin/env python3
"""Generate the raw ufbx binding from upstream's bindgen IR.

Usage:
    python3 scripts/gen_bindings.py           rewrite src/ufbx.c3i, src/layout.c3, scripts/abi-*.txt
    python3 scripts/gen_bindings.py --check   fail if any generated file differs from a fresh run

The IR comes from vendor/ufbx/bindgen (ufbx_parser.py, then ufbx_ir.py), which writes
vendor/ufbx/bindgen/build/ufbx_typed.json; that directory is ignored by upstream.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / "vendor" / "ufbx"
BINDGEN = VENDOR / "bindgen"
IR_PATH = BINDGEN / "build" / "ufbx_typed.json"
HEADER = VENDOR / "ufbx.h"

ARCH = "x64"

# Functions the idiomatic layer wraps under the plain name.
WRAPPED = {"ufbx_load_file", "ufbx_bake_anim", "ufbx_triangulate_face", "ufbx_generate_indices"}

PRIMITIVES = {
    "void": "void",
    "char": "char",
    "bool": "bool",
    "int8_t": "ichar",
    "uint8_t": "char",
    "int16_t": "short",
    "uint16_t": "ushort",
    "int32_t": "int",
    "uint32_t": "uint",
    "int64_t": "long",
    "uint64_t": "ulong",
    "size_t": "usz",
    "ptrdiff_t": "sz",
    "uintptr_t": "uptr",
    "float": "float",
    "double": "double",
    "UFBX_REAL_TYPE": "double",
    "ufbx_real": "double",
}

C3_KEYWORDS = {
    "alias", "any", "asm", "assert", "attrdef", "bitstruct", "break", "case", "catch", "const",
    "constdef", "continue", "default", "defer", "do", "else", "enum", "extern", "false", "fault",
    "faultdef", "fn", "for", "foreach", "foreach_r", "if", "import", "inline", "interface",
    "lengthof", "macro", "module", "nextcase", "null", "return", "static", "struct", "switch",
    "tlocal", "true", "try", "typedef", "typeid", "union", "var", "while",
}


def pascal(name):
    return "".join(part[:1].upper() + part[1:] for part in name.split("_") if part)


def strip_prefix(name):
    for prefix in ("ufbx_", "UFBX_"):
        if name.startswith(prefix):
            return name[len(prefix):]
    raise ValueError(f"unprefixed name {name}")


def field_name(name):
    return name + "_" if name in C3_KEYWORDS else name


class Generator:
    def __init__(self, ir):
        self.ir = ir
        self.types = ir["types"]
        self.structs = ir["structs"]
        self.enums = ir["enums"]
        self.enum_values = ir["enumValues"]
        self.list_elements = {}
        for name, struct in self.structs.items():
            if struct["isList"]:
                data = next(field for field in struct["fields"] if field["name"] == "data")
                self.list_elements[name] = self.pointee(data["type"])

    def pointee(self, key):
        return self.types[key]["inner"]

    def type_name(self, key):
        return pascal(strip_prefix(key))

    def enum_is_sequential(self, enum):
        values = [self.enum_values[value] for value in enum["values"]]
        plain = [value["value"] for value in values if not value["auxiliary"]]
        return not enum["flag"] and plain == list(range(len(plain)))

    def c3_type(self, key):
        if key in PRIMITIVES:
            return PRIMITIVES[key]
        info = self.types[key]
        kind = info["kind"]
        if kind in ("const", "unsafe"):
            return self.c3_type(info["inner"])
        if kind == "pointer":
            inner_key = info["inner"]
            inner = self.types.get(inner_key)
            if inner_key in ("char", "char const") or (inner and inner["kind"] == "const" and inner["inner"] == "char"):
                return "ZString"
            base = self.strip_nullable(inner_key)
            if base in self.types and self.types[base]["kind"] == "typedef" and self.is_function_typedef(base):
                return self.type_name(base)
            return self.c3_type(inner_key) + "*"
        if kind == "array":
            return f"{self.c3_type(info['inner'])}[{info['arrayLength']}]"
        if kind == "enum":
            return self.type_name(key)
        if kind == "typedef":
            if key in PRIMITIVES:
                return PRIMITIVES[key]
            return self.type_name(key)
        if kind == "struct":
            if key == "ufbx_string":
                return "String"
            if key == "ufbx_blob":
                return "char[]"
            if key in self.list_elements:
                return self.c3_type(self.list_elements[key]) + "[]"
            return self.type_name(key)
        if key.endswith("?"):
            return self.c3_type(key[:-1])
        raise ValueError(f"unmapped type {key} ({kind})")

    def strip_nullable(self, key):
        return key[:-1] if key.endswith("?") else key

    def is_function_typedef(self, key):
        target = self.ir["typedefs"][key]["type"]
        return self.types.get(target, {}).get("kind") == "function"

    # Declarations

    def emit_typedefs(self, out):
        for name, typedef in self.ir["typedefs"].items():
            if name in PRIMITIVES:
                continue
            target = self.types[typedef["type"]]
            if target["kind"] == "function":
                ret = self.c3_type(target["inner"])
                args = ", ".join(f"{self.c3_type(arg['type'])} {field_name(arg['name'])}" for arg in target["funcArgs"])
                out.append(f"alias {self.type_name(name)} = fn {ret} ({args});")
            else:
                out.append(f"typedef {self.type_name(name)} = {self.c3_type(typedef['type'])};")
        out.append("")

    def enum_value_name(self, enum, value_name):
        values = [value for value in enum["values"]]
        if len(values) == 1:
            prefix = enum["name"].upper() + "_"
        else:
            common = values[0]
            for value in values[1:]:
                while not value.startswith(common):
                    common = common[:-1]
            prefix = common[: common.rfind("_") + 1]
        rest = value_name[len(prefix):]
        if not rest or rest[0].isdigit():
            trimmed = prefix[:-1]
            rest = trimmed[trimmed.rfind("_") + 1:] + "_" + rest
        return rest

    def emit_enums(self, out):
        for name, enum in self.enums.items():
            c3_name = self.type_name(name)
            values = [self.enum_values[value] for value in enum["values"]]
            if self.enum_is_sequential(enum):
                plain = [value for value in values if not value["auxiliary"]]
                names = [self.enum_value_name(enum, value["name"]) for value in plain]
                if len(set(names)) != len(names):
                    raise ValueError(f"duplicate value names in {name}")
                out.append(f"enum {c3_name} : int {{")
                for value in names:
                    out.append(f"    {value},")
                out.append("}")
                out.append("")
                for value in values:
                    if not value["auxiliary"]:
                        continue
                    target = next(other for other in plain if other["value"] == value["value"])
                    out.append(
                        f"const {c3_name} {strip_prefix(value['name'])} = "
                        f"{c3_name}.{self.enum_value_name(enum, target['name'])};"
                    )
                if any(value["auxiliary"] for value in values):
                    out.append("")
            else:
                out.append(f"typedef {c3_name} = int;")
                for value in values:
                    out.append(f"const {c3_name} {strip_prefix(value['name'])} = ({c3_name}){value['value']};")
                out.append("")

    def emit_constants(self, out):
        for name, constant in self.ir["constants"].items():
            if "valueInt" not in constant:
                continue
            out.append(f"const {strip_prefix(name)} = {constant['valueInt']};")
        out.append("")

    def emit_fields(self, out, struct, indent):
        pad = "    " * indent
        for field in struct["fields"]:
            if field["name"] == "":
                nested = self.structs[field["type"]]
                out.append(f"{pad}{'union' if nested['isUnion'] else 'struct'} {{")
                self.emit_fields(out, nested, indent + 1)
                out.append(f"{pad}}}")
            else:
                out.append(f"{pad}{self.c3_type(field['type'])} {field_name(field['name'])};")

    def named_structs(self):
        for name, struct in self.structs.items():
            if struct["isAnonymous"] or struct["isList"] or name in ("ufbx_string", "ufbx_blob"):
                continue
            yield name, struct

    def emit_structs(self, out):
        for name, struct in self.named_structs():
            out.append(f"{'union' if struct['isUnion'] else 'struct'} {self.type_name(name)} {{")
            self.emit_fields(out, struct, 1)
            out.append("}")
            out.append("")

    def emit_globals(self, out):
        pattern = re.compile(r"^ufbx_abi_data const (\w+) (ufbx_\w+)(\[(\w+)\])?;", re.MULTILINE)
        for match in pattern.finditer(HEADER.read_text()):
            c_type, c_name, _, length = match.groups()
            c3 = self.c3_type(c_type)
            if length:
                c3 = f"{c3}[{strip_prefix(length)}]"
            out.append(f'extern {c3} {strip_prefix(c_name)} @cname("{c_name}");')
        out.append("")

    def emit_functions(self, out):
        for name, function in self.ir["functions"].items():
            if function["isInline"]:
                continue
            c3_name = strip_prefix(name) + ("_raw" if name in WRAPPED else "")
            ret = self.c3_type(function["returnType"])
            args = ", ".join(
                f"{self.c3_type(arg['type'])} {field_name(arg['name'])}" for arg in function["arguments"]
            )
            out.append(f'extern fn {ret} {c3_name}({args}) @cname("{name}");')
        out.append("")

    def interface(self):
        out = [
            "module ufbx;",
            "",
            f"// Generated by scripts/gen_bindings.py from ufbx {vendor_tag()}. Do not edit.",
            "",
        ]
        self.emit_typedefs(out)
        self.emit_constants(out)
        self.emit_enums(out)
        self.emit_structs(out)
        self.emit_globals(out)
        self.emit_functions(out)
        return "\n".join(out).rstrip("\n") + "\n"

    # Layout pins

    def field_offsets(self, struct, base):
        for field in struct["fields"]:
            offset = base + field["offset"][ARCH]
            if field["name"] == "":
                yield from self.field_offsets(self.structs[field["type"]], offset)
            else:
                yield field["name"], offset

    def layout(self):
        out = [
            "module ufbx;",
            "",
            f"// Generated by scripts/gen_bindings.py from ufbx {vendor_tag()}. Do not edit.",
            "",
        ]
        for name, struct in self.named_structs():
            c3_name = self.type_name(name)
            info = self.types[name]
            out.append(f"$assert {c3_name}::size == {info['size'][ARCH]};")
            out.append(f"$assert {c3_name}::alignment == {info['align'][ARCH]};")
            for field, offset in self.field_offsets(struct, 0):
                out.append(f"$assert $reflect({c3_name}.{field_name(field)}).offset == {offset};")
        return "\n".join(out) + "\n"

    def sizes(self):
        lines = []
        for name, _ in self.named_structs():
            info = self.types[name]
            lines.append(f"{name} {info['size'][ARCH]} {info['align'][ARCH]}")
        return "\n".join(lines) + "\n"

    def offsets(self):
        lines = []
        for name, struct in self.named_structs():
            for field, offset in self.field_offsets(struct, 0):
                lines.append(f"{name} {field} {offset}")
        return "\n".join(lines) + "\n"


def vendor_tag():
    match = re.search(r"#define UFBX_HEADER_VERSION ufbx_pack_version\((\d+), (\d+), (\d+)\)", HEADER.read_text())
    return "v{}.{}.{}".format(*match.groups())


def run_bindgen():
    subprocess.run([sys.executable, "ufbx_parser.py"], cwd=BINDGEN, check=True)
    subprocess.run([sys.executable, "ufbx_ir.py"], cwd=BINDGEN, check=True, stdout=subprocess.DEVNULL)


def outputs(generator):
    return {
        ROOT / "src" / "ufbx.c3i": generator.interface(),
        ROOT / "src" / "layout.c3": generator.layout(),
        ROOT / "scripts" / "abi-sizes.txt": generator.sizes(),
        ROOT / "scripts" / "abi-offsets.txt": generator.offsets(),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    options = parser.parse_args()

    if not HEADER.exists():
        sys.exit("vendor/ufbx is empty. Run: git submodule update --init")
    run_bindgen()
    generator = Generator(json.loads(IR_PATH.read_text()))
    files = outputs(generator)

    if options.check:
        stale = [path for path, text in files.items() if not path.exists() or path.read_text() != text]
        for path in stale:
            print(f"stale: {path.relative_to(ROOT)}", file=sys.stderr)
        if stale:
            sys.exit("generated files differ; run python3 scripts/gen_bindings.py")
        print("generated files match")
        return

    for path, text in files.items():
        path.write_text(text)
        print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
