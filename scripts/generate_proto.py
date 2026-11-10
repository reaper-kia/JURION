from pathlib import Path

import grpc_tools
from grpc_tools import protoc

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONTRACTS_DIR = PROJECT_ROOT / "contracts"
OUTPUT_DIR = PROJECT_ROOT / "packages" / "platform_contracts" / "src"


def main() -> None:
    if grpc_tools.__file__ is None:
        raise RuntimeError("Cannot locate grpc_tools installation")

    well_known_types_dir = Path(grpc_tools.__file__).resolve().parent / "_proto"
    proto_files = sorted(CONTRACTS_DIR.rglob("*.proto"))

    if not proto_files:
        raise RuntimeError(f"No .proto files found in {CONTRACTS_DIR}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    arguments = [
        "grpc_tools.protoc",
        f"--proto_path={CONTRACTS_DIR}",
        f"--proto_path={well_known_types_dir}",
        f"--python_out={OUTPUT_DIR}",
        f"--pyi_out={OUTPUT_DIR}",
        f"--grpc_python_out={OUTPUT_DIR}",
        *(str(path.relative_to(CONTRACTS_DIR)) for path in proto_files),
    ]

    exit_code = protoc.main(arguments)
    if exit_code != 0:
        raise SystemExit(exit_code)

    print(f"Generated {len(proto_files)} proto files into {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
