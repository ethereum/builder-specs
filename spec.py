from enum import IntEnum
from typing import Dict, NamedTuple, List, Sequence, Optional, TypeVar, Tuple

import ast
import os
import string

from marko.block import Heading, FencedCode, LinkRefDef, BlankLine
from marko.inline import CodeSpan
from marko.ext.gfm import gfm
from marko.ext.gfm.elements import Table
from pathlib import Path

def is_variable_constant(name: str) -> bool:
    if name[0] not in string.ascii_uppercase + '_':
        return False
    return all(map(lambda c: c in string.ascii_uppercase + '_' + string.digits, name[1:]))

class VariableDefinition(NamedTuple):
    type_name: Optional[str]
    value: str

def parse_variable_def(name: str, typed_value: str) -> VariableDefinition:
    typed_value = typed_value.strip()
    if '(' not in typed_value:
        return VariableDefinition(type_name=None, value=typed_value)

    i = typed_value.index('(')
    type_name = typed_value[:i]
    return VariableDefinition(type_name=type_name, value=typed_value)

class SpecObject(NamedTuple):
    functions: Dict[str, str]
    custom_types: Dict[str, str]
    constant_vars: Dict[str, VariableDefinition]
    ssz_objects: Dict[str, str]

def get_source_from_code_block(code: FencedCode) -> str:
    return code.children[0].children.strip()

def get_function_name_from_source(source: str) -> str:
    fn = ast.parse(source).body[0]
    return fn.name

def get_class_info_from_source(source: str) -> Tuple[str, Optional[str]]:
    class_def = ast.parse(source).body[0]
    base = class_def.bases[0]
    if isinstance(base, ast.Name):
        parent_class = base.id
    else:
        parent_class = None
    return class_def.name, parent_class

class TableCols(IntEnum):
    NAME = 0
    VALUE = 1

def get_spec(file_name: Path) -> SpecObject:
    functions: Dict[str, str] = {}
    constant_vars: Dict[str, VariableDefinition] = {}
    ssz_objects: Dict[str, str] = {}
    custom_types: Dict[str, str] = {}

    with open(file_name) as source_file:
        document = gfm.parse(source_file.read())

    for child in document.children:
        if isinstance(child, FencedCode):
            if child.lang != "python":
                continue
            source = get_source_from_code_block(child)
            if source.startswith("def"):
                function_name = get_function_name_from_source(source)
                function_def = "\n".join(line.rstrip() for line in source.splitlines())
                functions[function_name] = function_def
            elif source.startswith("class"):
                class_name, parent_class_name = get_class_info_from_source(source)
                if parent_class_name:
                    assert parent_class_name == "Container"
                ssz_objects[class_name] = "\n".join(line.rstrip() for line in source.splitlines())
        elif isinstance(child, Table):
            for row in child.children:
                cells = row.children
                assert len(cells) >= 2

                name = cells[TableCols.NAME].children[0].children
                value = cells[TableCols.VALUE].children[0].children

                if isinstance(value, list):
                    # marko parses `**X**` as a list `[X]`
                    value = value[0].children

                if not is_variable_constant(name):
                    # Check whether the (name, value) defines a custom type (i.e. type alias)
                    if value.startswith(("uint", "Bytes", "ByteList", "Union", "Vector", "List", "ByteVector")):
                        custom_types[name] = value
                    continue
                
                var_def = parse_variable_def(name, value)
                constant_vars[name] = var_def
        else:
            continue

    return SpecObject(
        functions=functions,
        custom_types=custom_types,
        constant_vars=constant_vars,
        ssz_objects=ssz_objects,
    )

def object_to_spec(spec: SpecObject) -> str:
    constant_vars = [f"{name} = {var.value}" if var.type_name is None else f"{name}: {var.type_name} = {var.value}" for (name, var) in spec.constant_vars.items()]
    spec = (
            "\n\n".join(spec.custom_types.values())
            + ("\n\n" if len(spec.custom_types) > 0 else "")
            + "\n".join(constant_vars)
            + ("\n\n" if len(spec.constant_vars) > 0 else "")
            + "\n\n".join(spec.ssz_objects.values())
            + ("\n\n" if len(spec.ssz_objects) > 0 else "")
            + "\n\n".join(spec.functions.values())
    )
    return spec

def combine_specs(x: SpecObject, y: SpecObject) -> SpecObject:
    functions = {**x.functions, **y.functions}
    custom_types = {**x.custom_types, **y.custom_types}
    constant_vars = {**x.constant_vars, **y.constant_vars}
    ssz_objects = {**x.ssz_objects, **y.ssz_objects}

    return SpecObject(
        functions=functions,
        custom_types=custom_types,
        constant_vars=constant_vars,
        ssz_objects=ssz_objects,
    )

def build_spec(files: Sequence[Path]) -> SpecObject:
    assert len(files) > 0
    specs = [get_spec(spec) for spec in files]

    assert len(specs) > 0
    total_spec = specs[0]
    for spec in specs[1:]:
        total_spec = combine_specs(total_spec, spec)

    return total_spec 

def spec_files(spec: str) -> Sequence[Path]:
    root = os.path.dirname(__file__)
    root = os.path.join(root, "specs", spec)

    spec_files = []
    for root, dirs, files in os.walk(root):
        for file in files:
            if file.endswith(".md"):
                spec_files.append(os.path.join(root, file))
    return spec_files

BELLATRIX_IMPORTS = [
        """from eth2spec.bellatrix.mainnet import (
            Attestation,
            AttesterSlashing,
            BLSPubkey,
            BLSSignature,
            Deposit,
            DomainType,
            Eth1Data,
            ExecutionAddress,
            ExecutionPayloadHeader,
            MAX_ATTESTATIONS,
            MAX_ATTESTER_SLASHINGS,
            MAX_DEPOSITS,
            MAX_PROPOSER_SLASHINGS,
            MAX_VOLUNTARY_EXITS,
            ProposerSlashing,
            Root,
            SignedVoluntaryExit,
            Slot,
            SyncAggregate,
            ValidatorIndex
        )""",
        "from eth2spec.utils.ssz.ssz_typing import (Bytes32, Container, List, uint64, uint256)"
]

CAPELLA_IMPORTS = ["from eth2spec.capella.mainnet import SignedBLSToExecutionChange"]

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--specs", dest="specs", nargs="+", type=Path)
    args = parser.parse_args()

    specs = args.specs
    files = [spec_files(spec) for spec in specs]
    spec = SpecObject(functions={}, custom_types={}, constant_vars={}, ssz_objects={})
    for (spec_name, spec_files) in zip(specs, files):
        latest_spec = build_spec(spec_files)
        spec = combine_specs(spec, latest_spec)
        dst = os.path.join("tests", "core", "pyspec", "builderspec")
        with open(os.path.join(dst, f"{spec_name}.py"), "w") as f:
            spec_src = object_to_spec(spec)

            spec_imports = []
            if str(spec_name) == "bellatrix":
                spec_imports = BELLATRIX_IMPORTS
            elif str(spec_name) == "capella":
                spec_imports = BELLATRIX_IMPORTS
                for imp in CAPELLA_IMPORTS:
                    spec_imports.append(imp)

            spec_imports = "\n".join(spec_imports)
            spec_src = "\n\n".join([spec_imports, spec_src])

            f.write(spec_src)
        with open(os.path.join(dst, "__init__.py"), "w") as f:
            pass
