"""Official-schema + reference-implementation validation of our SBOM output."""
import json, sys, os

sys.path.insert(0, os.path.abspath("."))
import jsonschema

print("=== 1. jsonschema vs official SPDX 2.3 + CycloneDX 1.5 schemas ===")
def _load(p):
    return json.load(open(p, encoding="utf-8"))

spdx = _load("sbom/output/sbom.spdx.json")
cdx = _load("sbom/output/sbom.cdx.json")

spdx_schema = _load("sbom/.xval/spdx-2.3.json")
cdx_schema = _load("sbom/.xval/cdx-1.5.json")

v = jsonschema.Draft7Validator(spdx_schema)
errs = sorted(v.iter_errors(spdx), key=lambda e: (list(e.path), e.message))
print(f"SPDX official schema: {len(errs)} error(s)")
for e in errs[:15]:
    print("   -", list(e.path), e.message)

v = jsonschema.Draft7Validator(cdx_schema)
cerrs = sorted(v.iter_errors(cdx), key=lambda e: (list(e.path), e.message))
print(f"CycloneDX official schema: {len(cerrs)} error(s)")
for e in cerrs[:15]:
    print("   -", list(e.path), e.message)

print("\n=== 2. spdx-tools (official SPDX reference implementation) ===")
try:
    from spdx_tools.spdx.parser.parse_anything import parse_file
    from spdx_tools.spdx.validation.document_validator import (
        validate_full_spdx_document,
    )

    doc, parse_msgs = parse_file("sbom/output/sbom.spdx.json")
    print("spdx-tools parse messages:", parse_msgs or "none")
    val_msgs = validate_full_spdx_document(doc)
    print(f"spdx-tools full validation: {len(val_msgs)} message(s)")
    for m in val_msgs[:15]:
        print("   -", m.validation_message)
except Exception as e:
    print("spdx-tools error:", type(e).__name__, e)

print("\n=== 3. cyclonedx-python-lib (official CycloneDX library) strict validation ===")
try:
    import json as _json
    from cyclonedx.schema import SchemaVersion
    from cyclonedx.validation.json import JsonStrictValidator

    raw = open("sbom/output/sbom.cdx.json", encoding="utf-8").read()
    v = JsonStrictValidator(SchemaVersion.V1_5)
    res = v.validate_str(raw)
    print(f"cyclonedx-python-lib strict: {len(res)} error(s)")
    for e in res[:15]:
        print("   -", str(e)[:200])
except Exception as e:
    print("cyclonedx error:", type(e).__name__, e)

print("\n=== 4. cyclonedx-python-lib parse (can the official lib ingest it?) ===")
try:
    from cyclonedx.model.bom import Bom
    from cyclonedx.validation.json import JsonValidator

    v = JsonValidator(SchemaVersion.V1_5)
    res = v.validate_str(open("sbom/output/sbom.cdx.json", encoding="utf-8").read())
    print(f"lenient parse validation: {len(res)} issue(s)")
    bom = Bom.from_json(open("sbom/output/sbom.cdx.json", encoding="utf-8").read())
    print(f"official lib loaded {len(bom.components)} components, "
          f"{len(bom.dependencies)} dependency entries")
except Exception as e:
    print("Bom.from_json error:", type(e).__name__, str(e)[:300])
