"""Non-executing checks for a standalone historical EdgeAI extraction.

Uses only the Python standard library. Does not import benchmark modules, build
firmware, run inference, or write benchmark results.
"""
import ast
import csv
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


class Tables(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables = []
        self.current = None
        self.row = None
        self.cell = None
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "table":
            self.current = {"align": attrs.get("align"), "rows": []}
        elif tag == "tr" and self.current is not None:
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.cell = ""
        if tag in ("a", "img"):
            self.links.append(attrs.get("href", attrs.get("src", "")))

    def handle_data(self, data):
        if self.cell is not None:
            self.cell += data

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None:
            self.row.append(self.cell.strip())
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.current["rows"].append(self.row)
            self.row = None
        elif tag == "table" and self.current is not None:
            self.tables.append(self.current)
            self.current = None


GEO_COLUMNS = {
    "latitude", "longitude", "country_name", "country_iso_code", "region", "cloud_region"
}


def verify_privacy_copies(manifest, errors):
    """Check public CSV projections without needing access to the source repository."""
    import uuid

    entries = [e for e in manifest["files"] if e.get("kind") == "privacy-reduced-columns"]
    actual_paths = {p.relative_to(ROOT).as_posix()
                    for p in (ROOT / "historical-results").rglob("emissions.csv")}
    targets = [e["target"] for e in manifest["files"]]
    if len(targets) != len(set(targets)):
        errors.append("Duplicate manifest targets")
    expected_count = 4 if (ROOT / "LLM").is_dir() else 5
    if len(entries) != expected_count or {e["target"] for e in entries} != actual_paths:
        errors.append("CodeCarbon privacy entries must cover every historical emissions.csv")
    row_count = 0
    for entry in entries:
        target = entry["target"]
        path = (ROOT / target).resolve()
        if not path.is_relative_to(ROOT.resolve()) or not path.is_file():
            errors.append("Invalid privacy-copy path: " + target)
            continue
        try:
            with path.open(encoding="utf-8-sig", newline="") as handle:
                parsed = list(csv.reader(handle))
            header, rows = parsed[0], parsed[1:]
            if not header or any(not x.strip() for x in header) or len(header) != len(set(header)):
                raise ValueError("blank or duplicate headers")
            if any(len(row) != len(header) for row in rows):
                raise ValueError("ragged CSV row")
            if any(x.strip().casefold() in GEO_COLUMNS for x in header):
                raise ValueError("geographic column remains")
            if header != entry["retained_columns"]:
                raise ValueError("retained column order changed")
            removed = entry["removed_columns"]
            if len(removed) != len(GEO_COLUMNS) or set(removed) != GEO_COLUMNS:
                raise ValueError("unexpected removed columns")
            required = {"timestamp", "run_id", "duration", "emissions", "emissions_rate",
                        "cpu_power", "gpu_power", "ram_power", "cpu_energy", "gpu_energy",
                        "ram_energy", "energy_consumed"}
            if not required.issubset(header):
                raise ValueError("missing provenance or measurement fields")
            for name in ("run_id", "experiment_id"):
                if name in header:
                    index = header.index(name)
                    for row in rows:
                        if row[index]:
                            uuid.UUID(row[index])
            if len(rows) != entry["row_count"]:
                raise ValueError("row count changed")
            canonical = json.dumps([header, *rows], ensure_ascii=False,
                                   separators=(",", ":")).encode("utf-8")
            if hashlib.sha256(canonical).hexdigest() != entry["retained_values_sha256"]:
                raise ValueError("retained source values or row order changed")
            if not re.fullmatch(r"[0-9a-f]{64}", entry["source_sha256"]):
                raise ValueError("invalid original Git-blob hash")
            if not isinstance(entry["source_bytes"], int) or entry["source_bytes"] <= 0:
                raise ValueError("invalid original byte count")
            row_count += len(rows)
        except (OSError, ValueError, KeyError, IndexError) as error:
            errors.append("CodeCarbon privacy check: " + target + ": " + str(error))
    return len(entries), row_count


def main():
    errors = []
    files = []
    for directory, subdirectories, filenames in os.walk(ROOT):
        subdirectories[:] = [name for name in subdirectories if name != ".git"]
        files.extend(Path(directory) / name for name in filenames)
    manifest = json.loads((ROOT / "SOURCE_MANIFEST.json").read_text(encoding="utf-8"))
    for entry in manifest["files"]:
        path = (ROOT / entry["target"]).resolve()
        if not path.is_relative_to(ROOT.resolve()) or not path.is_file():
            errors.append("Invalid manifest path: " + entry["target"])
        else:
            data = path.read_bytes()
            if hashlib.sha256(data).hexdigest() != entry["sha256"] or len(data) != entry["bytes"]:
                errors.append("Manifest hash/size mismatch: " + entry["target"])
    privacy_files, privacy_rows = verify_privacy_copies(manifest, errors)

    local_modules = {"train", "eval_functions_eembc", "keras_model", "get_dataset",
                     "kws_util", "vww_model_updated", "results_helper", "esp32_energy_helper"}
    python_files = [p for p in files if p.suffix == ".py"]
    for path in python_files:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
            compile(tree, str(path), "exec")
        except (SyntaxError, UnicodeError) as error:
            errors.append("Python syntax: " + str(error))
            continue
        for node in ast.walk(tree):
            modules = []
            if isinstance(node, ast.Import):
                modules = [item.name.split(".")[0] for item in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module.split(".")[0]]
            for module in modules:
                if module in local_modules and not any(
                    (parent / (module + ".py")).is_file()
                    for parent in (path.parent, path.parent.parent)
                ):
                    errors.append("Missing local dependency: " + str(path.relative_to(ROOT)) + " -> " + module)

    local_link_count = 0
    for path in [p for p in files if p.suffix == ".md" and p.name != "LICENSE.md"]:
        content = re.sub(r"(?ms)^"+chr(96)*3+r".*?^"+chr(96)*3+r"[ \t]*$", "", path.read_text(encoding="utf-8"))
        parser = Tables()
        parser.feed(content)
        links = parser.links + re.findall(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+[^)]*)?\)", content)
        for link in links:
            parsed = urlsplit(link)
            if parsed.scheme or not parsed.path:
                continue
            local_link_count += 1
            dest = (path.parent / unquote(parsed.path)).resolve()
            if not dest.is_relative_to(ROOT.resolve()) or not dest.exists():
                errors.append("Broken or external local link: " + str(path.relative_to(ROOT)) + " -> " + link)

    parser = Tables()
    parser.feed((ROOT / "README.md").read_text(encoding="utf-8"))
    for table in parser.tables:
        if table["align"] != "center":
            errors.append("Root README has a table without align=center")
        widths = {len(row) for row in table["rows"]}
        if len(widths) != 1:
            errors.append("Root README table has inconsistent columns")

    summary = ROOT / "historical-results/MLPerf_Tiny/mlperf_tiny_all_devices_summary.csv"
    if summary.exists():
        from decimal import Decimal
        rows = list(csv.DictReader(summary.open(encoding="utf-8-sig", newline="")))
        result_tables = [t for t in parser.tables if t["rows"][0][0] == "Configuration"]
        if len(rows) != 6 or len(result_tables) != 1:
            errors.append("Expected six TinyML summary/table configurations")
        else:
            actual = {tuple(r) for r in result_tables[0]["rows"][1:]}
            expected = set()
            for row in rows:
                label = row["Device"]
                if label == "Raspberry Pi 5":
                    label += " - " + ("INT8" if row["Model"].endswith(".tflite") else "full precision")
                expected.add((label, format(Decimal(row["Accuracy"]) * 100, ".1f"),
                              row["Inference Time (s)"], row["Throughput"],
                              row["Carbon Emissions (kgCO2e)"]))
            if actual != expected:
                errors.append("README TinyML result values differ from recorded CSV")
    else:
        summary = ROOT / "historical-results/LLM/LLM_Bench_Results.csv"
        rows = list(csv.DictReader(summary.open(encoding="utf-8-sig", newline="")))
        rate_tables = [t for t in parser.tables if t["rows"][0][0] == "Device"]
        if len(rows) != 20 or not rate_tables:
            errors.append("Expected 20 LLM summary records and rate table")
        else:
            rate_table = next((t for t in rate_tables if "Knowledge Retrieval" in t["rows"][0]), None)
            if rate_table is None:
                errors.append("Missing LLM generation-rate table")
            else:
                categories = rate_table["rows"][0][1:]
                expected = {(r["Device"], r["Workload Category"]): r["Average Evaluation Rate (tokens/s)"] for r in rows}
                for row in rate_table["rows"][1:]:
                    for category, value in zip(categories, row[1:]):
                        if expected.get((row[0], category)) != value:
                            errors.append("LLM table mismatch: " + row[0] + "/" + category)

    firmware_count = 0
    for firmware in ROOT.glob("MLPerf_Tiny/*/training/*/firmware"):
        firmware_count += 1
        required = ["CMakeLists.txt", "README.md", "sdkconfig.defaults", "partitions.csv",
                    "dependencies.lock", "main/idf_component.yml", "main/CMakeLists.txt",
                    "main/main.cc", "main/main_functions.cc", "main/model.cc", "main/model.h",
                    "main/constants.cc", "main/constants.h", "main/main_functions.h",
                    "main/output_handler.cc", "main/output_handler.h"]
        for name in required:
            if not (firmware / name).is_file():
                errors.append("Missing firmware file: " + name)
        defaults = (firmware / "sdkconfig.defaults").read_text()
        for token in ['CONFIG_IDF_TARGET="esp32s3"', "CONFIG_ESPTOOLPY_FLASHSIZE_16MB=y",
                      "CONFIG_SPIRAM_MODE_OCT=y", "CONFIG_SPIRAM_SPEED_80M=y",
                      "CONFIG_ESP_DEFAULT_CPU_FREQ_MHZ_240=y", "CONFIG_PARTITION_TABLE_CUSTOM=y"]:
            if token not in defaults:
                errors.append("Missing firmware setting: " + token)
        lock = (firmware / "dependencies.lock").read_text()
        for token in ["6.0.3", "1.4.0", "1.3.2"]:
            if token not in lock:
                errors.append("Missing locked firmware version: " + token)
        model_text = (firmware / "main/model.cc").read_text()
        embedded = bytes(int(x, 16) for x in re.findall(r"\b0x([0-9a-fA-F]{2})\b", model_text))
        models = list((firmware.parent / "trained_models").glob("*.tflite"))
        if len(models) != 1 or models[0].read_bytes() != embedded:
            errors.append("Embedded and host INT8 model mismatch")
        invoke = (firmware / "main/main_functions.cc").read_text()
        if "interpreter->Invoke()" not in invoke or "esp_timer_get_time()" not in invoke:
            errors.append("Missing invocation/timer structure")
        cmake = (firmware / "main/CMakeLists.txt").read_text()
        for src in re.findall(r'"([^"]+\.(?:cc|cpp|c))"', cmake):
            if not (firmware / "main" / src).is_file():
                errors.append("CMake source missing: " + src)

    forbidden_parts = {"build", "managed_components", "__pycache__", ".venv", "venv",
                       "benchmark_data", "results_new", "Previous", ".git",
                       "cifar-10-batches-py", "cifar-10-python", "vw_coco2014_96"}
    secrets = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|"
                         r"\bgh[pousr]_[A-Za-z0-9]{30,}\b|\bAKIA[A-Z0-9]{16}\b|"
                         r"\bsk-proj-[A-Za-z0-9_-]{40,}\b")
    for path in files:
        relative = path.relative_to(ROOT)
        if set(relative.parts) & forbidden_parts or path.name in {"sdkconfig", "sdkconfig.old"}:
            errors.append("Unwanted generated/dataset/Git path: " + str(relative))
        if path.suffix.lower() in {".zip", ".rar", ".tar", ".gz", ".xlsx", ".pdf", ".docx", ".pyc"}:
            errors.append("Unwanted archive/document: " + str(relative))
        if path.stat().st_size >= 50 * 1024 * 1024:
            errors.append("File at least 50 MiB: " + str(relative))
        if path.suffix in {".py", ".md", ".txt", ".json", ".yml", ".cc", ".h"}:
            if secrets.search(path.read_text(encoding="utf-8", errors="replace")):
                errors.append("Potential secret: " + str(relative))
    report = {"source_commit": manifest["source_commit"], "files": len(files),
              "manifest_entries": len(manifest["files"]), "privacy_reduced_files": privacy_files,
              "privacy_rows_checked": privacy_rows, "python_files_checked": len(python_files),
              "local_document_links_checked": local_link_count, "centered_readme_tables": len(parser.tables),
              "summary_records": len(rows), "firmware_projects": firmware_count,
              "total_bytes": sum(p.stat().st_size for p in files),
              "largest_file_bytes": max(p.stat().st_size for p in files), "errors": errors}
    print(json.dumps(report, indent=2))
    raise SystemExit(bool(errors))


if __name__ == "__main__":
    main()
