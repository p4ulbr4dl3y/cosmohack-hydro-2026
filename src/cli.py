"""Точка входа CLI для HydroWatch Amur."""

from __future__ import annotations

import argparse
import json
import logging
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

try:
    import resource
except ImportError:  # pragma: no cover
    resource = None

import pandas as pd

from src.audit import generate_flood_audit_certificate
from src.data_fetch import DATA_URL, missing_s1_pairs, safe_extract
from src.evaluate import main as evaluate_main
from src.predict import main as predict_main
from src.predict import process_pair
from src.service.data_loader import DataLoader
from src.uncertainty import compute_flood_area_uncertainty

logger = logging.getLogger(__name__)

#: Читаемая подсказка, выводимая при отсутствии сцен Sentinel-1 (они
#: распространяются вне git-репозитория, см. docs/Ссылка на данные.txt).
DATA_DOWNLOAD_HINT = f"""\
Sentinel-1 scenes are required to run prediction, but they are NOT in this
git repository (see .gitignore: hydrowatch_amur/rasters/**/S1_*.tif).

Fetch the full case dataset first:

    uv run python -m src.cli fetch

(Downloads the archive from Google Drive and unpacks it; requires no external
``unzip`` binary. The link is also documented in docs/Ссылка на данные.txt.)
Google Drive link (one-time ~2.9 GB download, internet required):
    {DATA_URL}
After unpacking, hydrowatch_amur/rasters/ must contain the S1_pre_*.tif /
S1_peak_*.tif scenes referenced by hydrowatch_amur/pairs.csv.
Prediction is therefore NOT reproducible offline until this download is done.
"""


def run_report(pair_id: str | None = None, output: Path | None = None) -> None:
    """Формирует сводный отчёт для одной или всех пар."""
    loader = DataLoader()
    pairs = loader.get_pairs()
    if pair_id:
        pairs = [p for p in pairs if p["pair_id"] == pair_id]
        if not pairs:
            print(f"Error: Pair '{pair_id}' not found.", file=sys.stderr)
            sys.exit(1)

    reports = []
    for p in pairs:
        rep = loader.get_report(p["pair_id"])
        if rep:
            reports.append(rep)

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        if str(output).endswith(".csv"):
            rows = []
            for r in reports:
                lc = r.get("landcover", {})
                unc = r.get("uncertainty", {}) or {}
                aud = r.get("audit", {}) or {}
                sar = r.get("sar_analytics", {}) or {}
                carb = r.get("carbon_impact", {}) or {}
                cred = carb.get("credit_potential", {}) or {}
                comp = r.get("competition_score", {}) or {}
                rows.append(
                    {
                        "pair_id": r["pair_id"],
                        "aoi_id": r["aoi_id"],
                        "aoi_name": r["aoi_name"],
                        "event_id": r["event_id"],
                        "event_name": r["event_name"],
                        "flood_ha": r["flood_ha"],
                        "flood_km2": r["flood_km2"],
                        "water_pre_ha": r["water_pre_ha"],
                        "water_peak_ha": r["water_peak_ha"],
                        "water_gain_ha": r["water_gain_ha"],
                        "water_gain_pct": r["water_gain_pct"],
                        "builtup_ha": lc.get("builtup_ha", 0.0),
                        "cropland_ha": lc.get("cropland_ha", 0.0),
                        "natural_vegetation_ha": lc.get("natural_vegetation_ha", 0.0),
                        "uncertainty_ci_lower_ha": unc.get("lower_bound_ha", ""),
                        "uncertainty_ci_upper_ha": unc.get("upper_bound_ha", ""),
                        "uncertainty_margin_ha": unc.get("margin_ha", ""),
                        "uncertainty_rel_pct": unc.get("relative_uncertainty_pct", ""),
                        "merkle_root_sha256": aud.get("merkle_root", ""),
                        "merkle_verified": aud.get("status", "") == "verified",
                        "sar_mean_vv_db": sar.get("mean_vv_db", ""),
                        "sar_mean_vh_db": sar.get("mean_vh_db", ""),
                        "sar_radar_contrast_db": sar.get("radar_contrast_db", ""),
                        "carbon_loss_tC": carb.get("carbon_loss_tC", ""),
                        "emissions_equivalent_tCO2e": carb.get("emissions_equivalent_tCO2e", ""),
                        "carbon_credits_Q": cred.get("Q_credits", ""),
                        "competition_q_flood": comp.get("q_flood", ""),
                    }
                )
            pd.DataFrame(rows).to_csv(output, index=False)
            print(f"Report CSV saved to {output}")
        else:
            with open(output, "w", encoding="utf-8") as f:
                json.dump(reports if len(reports) > 1 else reports[0], f, indent=2, ensure_ascii=False)
            print(f"Report JSON saved to {output}")
    else:
        for r in reports:
            print("=" * 60)
            print(f"REPORT: {r['pair_id']} ({r['aoi_name']})")
            print(f"  Event: {r['event_name']} ({r['year']})")
            print(f"  Flood: {r['flood_ha']:.2f} ha ({r['flood_km2']:.2f} km²)")
            print(f"  Water Pre: {r['water_pre_ha']:.2f} ha | Peak: {r['water_peak_ha']:.2f} ha")
            print(f"  Water Gain: {r['water_gain_ha']:.2f} ha ({r['water_gain_pct']:.2f}%)")
            lc = r.get("landcover", {})
            print(f"  Builtup flood: {lc.get('builtup_ha', 0.0):.2f} ha ({lc.get('builtup_pct', 0.0):.1f}%)")
            print(f"  Cropland flood: {lc.get('cropland_ha', 0.0):.2f} ha ({lc.get('cropland_pct', 0.0):.1f}%)")
            print(
                f"  Natural flood: {lc.get('natural_vegetation_ha', 0.0):.2f} ha ({lc.get('natural_vegetation_pct', 0.0):.1f}%)"
            )
            print(f"  Mean HAND: {lc.get('mean_hand_m', 0.0):.2f} m")
            depth = r.get("depth_statistics", {})
            if (
                depth
                and depth.get("low_risk_ha", 0.0) + depth.get("medium_risk_ha", 0.0) + depth.get("high_risk_ha", 0.0)
                > 0
            ):
                print(
                    f"  MCHS Traversability Risk: Low (<0.5m): {depth.get('low_risk_ha', 0.0):.1f} ha ({depth.get('low_risk_pct', 0.0):.1f}%) | "
                    f"Med (0.5-1.5m): {depth.get('medium_risk_ha', 0.0):.1f} ha ({depth.get('medium_risk_pct', 0.0):.1f}%) | "
                    f"High (>1.5m): {depth.get('high_risk_ha', 0.0):.1f} ha ({depth.get('high_risk_pct', 0.0):.1f}%)"
                )
            gauge = r.get("gauge_status")
            if gauge:
                print(
                    f"  Gauge ({gauge.get('station_name', '')} / {gauge.get('river', '')}): "
                    f"{gauge.get('observed_level_cm')} cm (NPU: {gauge.get('npu_cm')} cm, OYA: {gauge.get('oya_cm')} cm) -> Stage: {gauge.get('stage_risk')}"
                )
            unc = r.get("uncertainty")
            if unc:
                print(
                    f"  Uncertainty (95% CI): [{unc['lower_bound_ha']:.2f}, {unc['upper_bound_ha']:.2f}] ha (±{unc['relative_uncertainty_pct']:.2f}%)"
                )
            aud = r.get("audit")
            if aud:
                print(
                    f"  Merkle Audit: {aud.get('status', 'unknown').upper()} (root: {str(aud.get('merkle_root', ''))[:16]}...)"
                )
            carb = r.get("carbon_impact")
            if carb:
                print(
                    f"  Carbon Loss: {carb.get('carbon_loss_tC', 0.0):.1f} t C (≈ {carb.get('emissions_equivalent_tCO2e', 0.0):.1f} t CO2e)"
                )
        print("=" * 60)


def run_audit(pair_id: str, output_json: Path | None = None) -> dict[str, Any]:
    """Формирует криптографический сертификат проверки Merkle для наблюдаемой пары."""
    loader = DataLoader()
    rep = loader.get_report(pair_id)
    if not rep:
        print(f"Error: Pair '{pair_id}' not found.", file=sys.stderr)
        sys.exit(1)

    meta = loader.get_pair_meta(pair_id) or {}
    inputs_info = {
        "pair_id": pair_id,
        "aoi_id": rep.get("aoi_id"),
        "date_pre": rep.get("date_pre_sar"),
        "date_peak": rep.get("date_peak_sar"),
        "rasters_dir": str(meta.get("rasters_dir", "")),
    }
    params = {
        "otsu_corridor_db": [-22.0, -12.0],
        "mmu_min_pixels": 25,
        "speckle_filter": "Lee-MMSE-7x7",
    }
    summary = {
        "flood_ha": rep.get("flood_ha", 0.0),
        "water_peak_ha": rep.get("water_peak_ha", 0.0),
        "water_pre_ha": rep.get("water_pre_ha", 0.0),
    }
    cert = generate_flood_audit_certificate(
        pair_id=pair_id,
        aoi_id=rep.get("aoi_id", "AOI"),
        inputs_info=inputs_info,
        parameters=params,
        results_summary=summary,
    )
    cert_dict = cert.to_dict()

    print("\n" + "=" * 60)
    print(f"HYDRO AUDIT CERTIFICATE: {cert.certificate_id}")
    print("=" * 60)
    print(f"Pair ID:       {cert.pair_id}")
    print(f"Issued At:     {cert.issued_at}")
    print(f"Merkle Root:   {cert.merkle_root}")
    print(f"Signature:     {cert.signature_hash}")
    print(f"Status:        {cert.status}")
    print(f"Flood Area:    {summary['flood_ha']:.2f} ha")
    print("=" * 60 + "\n")

    if output_json:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(cert_dict, f, indent=2, ensure_ascii=False)
        print(f"Audit certificate saved to {output_json}\n")

    return cert_dict


def run_uncertainty(
    pair_id: str,
    confidence_level: float = 0.95,
    spatial_correlation: float = 0.20,
    output_json: Path | None = None,
) -> dict[str, Any]:
    """Вычисляет пространственную неопределённость и доверительный интервал [L, U] для наблюдаемой пары."""
    import numpy as np

    loader = DataLoader()
    rep = loader.get_report(pair_id)
    if not rep:
        print(f"Error: Pair '{pair_id}' not found.", file=sys.stderr)
        sys.exit(1)

    flood_ha = float(rep.get("flood_ha", 0.0))
    n_pixels = int(round(flood_ha / 0.01))
    dummy_mask = np.ones(n_pixels, dtype=bool) if n_pixels > 0 else np.zeros(0, dtype=bool)
    res = compute_flood_area_uncertainty(
        dummy_mask,
        pixel_area_ha=0.01,
        spatial_correlation=spatial_correlation,
        confidence_level=confidence_level,
    )

    out = {
        "pair_id": pair_id,
        "flood_area_ha": res.area_ha,
        "confidence_level": res.confidence_level,
        "lower_bound_ha": res.lower_bound_ha,
        "upper_bound_ha": res.upper_bound_ha,
        "margin_ha": res.margin_ha,
        "relative_uncertainty_pct": res.relative_uncertainty_pct,
        "sigma_effective_ha": res.sigma_effective_ha,
        "effective_n_pixels": res.effective_n_pixels,
        "spatial_correlation": res.spatial_correlation,
    }

    print("\n" + "=" * 60)
    print(f"SPATIAL UNCERTAINTY ANALYSIS: {pair_id}")
    print("=" * 60)
    print(f"Flood Area:             {res.area_ha:.2f} ha")
    print(f"Confidence Level:       {res.confidence_level * 100:.1f}% (z = {res.z_score})")
    print(f"Confidence Interval:    [{res.lower_bound_ha:.2f}, {res.upper_bound_ha:.2f}] ha")
    print(f"Absolute Margin (H):    ±{res.margin_ha:.2f} ha")
    print(f"Relative Uncertainty:   ±{res.relative_uncertainty_pct:.2f}%")
    print(f"Spatial Error Rho:      {res.spatial_correlation:.2f}")
    print("=" * 60 + "\n")

    if output_json:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)
        print(f"Uncertainty summary saved to {output_json}\n")

    return out


def run_manifest(
    output_path: Path | None = None,
    verify: bool = False,
    base_dir: Path | None = None,
    targets: list[str] | None = None,
) -> dict[str, Any] | None:
    """Генерирует или проверяет манифест целостности SHA-256 артефактов."""
    from src.manifest import DEFAULT_MANIFEST_PATH, generate_manifest, verify_manifest

    out = output_path or DEFAULT_MANIFEST_PATH
    base = base_dir or Path(".")

    if verify:
        result = verify_manifest(out, base_dir=base)
        print(result.summary())
        if not result.is_valid:
            sys.exit(1)
        return None
    else:
        manifest = generate_manifest(targets=targets, base_dir=base, output_path=out)
        print(f"Artifacts manifest generated successfully: {out}")
        print(f"  Total artifacts : {manifest['total_files']}")
        print(f"  Total size      : {manifest['total_size_bytes'] / (1024 * 1024):.2f} MB")
        print(f"  Merkle root     : {manifest['merkle_root']}")
        return manifest


def run_benchmark(
    pairs_csv_path: Path,
    data_dir: Path,
    predictions_dir: Path,
    iterations: int = 1,
    output_json: Path | None = None,
) -> dict[str, float]:
    """Измеряет задержку инференса и пропускную способность памяти."""
    if not pairs_csv_path.exists():
        print(f"Error: pairs CSV not found at {pairs_csv_path}", file=sys.stderr)
        sys.exit(1)

    pairs_df = pd.read_csv(pairs_csv_path)
    total_pairs = len(pairs_df)
    times = []

    print(f"Benchmarking HydroWatch inference across {total_pairs} pairs ({iterations} iteration(s))...")

    # Временные растры пишутся во временный каталог, чтобы бенчмарк работал и на read-only копиях
    with tempfile.TemporaryDirectory(prefix="hydrowatch_benchmark_") as tmp_dir:
        tmp_out = Path(tmp_dir)
        for _i in range(iterations):
            for idx, row in pairs_df.iterrows():
                t0 = time.perf_counter()
                process_pair(
                    row=row,
                    data_dir=data_dir,
                    predictions_dir=tmp_out,
                    ablation_mode=4,
                )
                elapsed = time.perf_counter() - t0
                times.append(elapsed)
                print(f"  [{idx + 1}/{total_pairs}] {row['pair_id']}: {elapsed:.3f}s")

    avg_time = sum(times) / len(times)
    total_time = sum(times)
    fps = len(times) / total_time

    # Пиковый RSS: macOS возвращает байты, Linux возвращает KiB, Windows использует GetProcessMemoryInfo
    if resource is not None:
        ru_maxrss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        peak_mb = (ru_maxrss / (1024.0 * 1024.0)) if sys.platform == "darwin" else (ru_maxrss / 1024.0)
    elif sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            class _PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            _pmc = _PROCESS_MEMORY_COUNTERS()
            _pmc.cb = ctypes.sizeof(_PROCESS_MEMORY_COUNTERS)
            _k32 = ctypes.WinDLL("kernel32")
            _k32.GetCurrentProcess.restype = wintypes.HANDLE
            _psapi = ctypes.WinDLL("psapi")
            _psapi.GetProcessMemoryInfo.argtypes = [
                wintypes.HANDLE,
                ctypes.POINTER(_PROCESS_MEMORY_COUNTERS),
                wintypes.DWORD,
            ]
            _psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
            if _psapi.GetProcessMemoryInfo(_k32.GetCurrentProcess(), ctypes.byref(_pmc), _pmc.cb):
                peak_mb = _pmc.PeakWorkingSetSize / (1024.0 * 1024.0)
            else:
                peak_mb = 1.0
        except Exception:
            peak_mb = 1.0
    else:
        peak_mb = 0.0

    print("\n" + "=" * 50)
    print("BENCHMARK RESULTS")
    print("=" * 50)
    print(f"Total processed scenes: {len(times)}")
    print(f"Total pipeline time:    {total_time:.2f} s")
    print(f"Average latency:        {avg_time:.3f} s / pair")
    print(f"Throughput:             {fps:.2f} pairs / sec")
    print(f"Peak RAM (ru_maxrss):   {peak_mb:.1f} MB")
    print("=" * 50 + "\n")

    summary = {
        "scenes_processed": float(len(times)),
        "total_pipeline_s": round(total_time, 2),
        "avg_latency_s_per_pair": round(avg_time, 3),
        "throughput_pairs_per_s": round(fps, 2),
        "peak_rss_mb": round(peak_mb, 1),
        "gpu_vram_mb": 0.0,
    }

    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        with open(output_json, "w", encoding="utf-8") as fp:
            json.dump(summary, fp, indent=2, ensure_ascii=False)
        print(f"Benchmark summary saved to {output_json}\n")

    return summary


def check_s1_data_available(pairs_csv_path: Path, data_dir: Path) -> bool:
    """Возвращает True, когда все сцены S1 pre/peak, указанные в pairs.csv, существуют."""
    missing = missing_s1_pairs(pairs_csv_path, data_dir)
    if missing:
        logger.warning(
            f"S1 scenes missing for {len(missing)} pairs: {', '.join(missing[:5])}" + ("…" if len(missing) > 5 else "")
        )
        return False
    return True


def run_fetch(
    pairs_csv_path: Path,
    data_dir: Path,
    archive_output: Path | None = None,
    keep_archive: bool = True,
) -> None:
    """Скачивает датасет кейса с Google Drive и распаковывает его."""
    import gdown

    archive_path = archive_output or data_dir.parent / "hydrowatch_amur_dataset.zip"
    if archive_path.exists():
        print(f"Archive already present: {archive_path} (skip download)", file=sys.stderr)
    else:
        print(f"Downloading dataset ({DATA_URL}) ...", file=sys.stderr)
        gdown.download(DATA_URL, str(archive_path), quiet=False)

    print(f"Unpacking to {data_dir} ...", file=sys.stderr)
    count = safe_extract(archive_path, data_dir)
    print(f"Extracted {count} entries into {data_dir}", file=sys.stderr)

    missing = missing_s1_pairs(pairs_csv_path, data_dir)
    if missing:
        print(
            f"Warning: S1 scenes still missing for {len(missing)} pairs: {', '.join(missing)}",
            file=sys.stderr,
        )

    if not keep_archive:
        archive_path.unlink(missing_ok=True)
        print(f"Removed archive {archive_path}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="hydrowatch-cli",
        description="HydroWatch Amur CLI: Predict, Evaluate, Report, and Benchmark Tools",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # подкоманда predict
    predict_parser = subparsers.add_parser(
        "predict", help="Run batch prediction on all pairs and generate submission.csv"
    )
    predict_parser.add_argument("--pairs", type=Path, default=Path("hydrowatch_amur/pairs.csv"))
    predict_parser.add_argument("--data-dir", type=Path, default=Path("hydrowatch_amur"))
    predict_parser.add_argument("--output-csv", type=Path, default=Path("submission.csv"))
    predict_parser.add_argument("--predictions-dir", type=Path, default=Path("predictions"))
    predict_parser.add_argument("--ablation-mode", type=int, default=4, choices=[1, 2, 3, 4])
    predict_parser.add_argument(
        "--workers",
        "--jobs",
        dest="workers",
        type=int,
        default=None,
        help="Number of worker processes for parallel batch inference (default: auto)",
    )

    # подкоманда evaluate
    eval_parser = subparsers.add_parser(
        "evaluate", help="Compute official score and raster metrics against reference masks"
    )
    eval_parser.add_argument("--pairs", type=Path, default=Path("hydrowatch_amur/pairs.csv"))
    eval_parser.add_argument("--data-dir", type=Path, default=Path("hydrowatch_amur"))
    eval_parser.add_argument("--submission-csv", type=Path, default=Path("submission.csv"))
    eval_parser.add_argument("--predictions-dir", type=Path, default=Path("predictions"))
    eval_parser.add_argument("--run-ablations", action="store_true", help="Run all 4 ablations")
    eval_parser.add_argument(
        "--holdout",
        action="store_true",
        help="Run the additional spatial leave-one-AOI-out (LOAO) hold-out diagnostic",
    )

    # подкоманда report
    report_parser = subparsers.add_parser("report", help="Generate hydrological report for a pair or all pairs")
    report_parser.add_argument("--pair-id", type=str, default=None, help="Target pair identifier")
    report_parser.add_argument("--output", type=Path, default=None, help="Output file path (.json or .csv)")

    # подкоманда fetch
    fetch_parser = subparsers.add_parser("fetch", help="Download the case dataset from Google Drive and unpack it")
    fetch_parser.add_argument("--pairs", type=Path, default=Path("hydrowatch_amur/pairs.csv"))
    fetch_parser.add_argument("--data-dir", type=Path, default=Path("hydrowatch_amur"))
    fetch_parser.add_argument(
        "--archive-output",
        type=Path,
        default=None,
        help="Local path for the downloaded zip (default: ./hydrowatch_amur_dataset.zip)",
    )
    fetch_parser.add_argument(
        "--no-keep-archive",
        action="store_true",
        help="Delete the downloaded archive after extraction",
    )

    # подкоманда benchmark
    bench_parser = subparsers.add_parser("benchmark", help="Benchmark pipeline latency and throughput")
    bench_parser.add_argument("--pairs", type=Path, default=Path("hydrowatch_amur/pairs.csv"))
    bench_parser.add_argument("--data-dir", type=Path, default=Path("hydrowatch_amur"))
    bench_parser.add_argument("--predictions-dir", type=Path, default=Path("predictions"))
    bench_parser.add_argument("--iterations", type=int, default=1, help="Number of benchmark iterations")
    bench_parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("data/benchmark_results.json"),
        help="Where to store the machine-readable benchmark summary",
    )

    # подкоманда fetch-optical
    fetch_opt_parser = subparsers.add_parser(
        "fetch-optical",
        help="Download and reproject real Sentinel-2 MSI L2A bands via Planetary Computer STAC",
    )
    fetch_opt_parser.add_argument("--pairs", type=Path, default=Path("hydrowatch_amur/pairs.csv"))
    fetch_opt_parser.add_argument("--pair-id", type=str, default=None, help="Process single pair_id")
    fetch_opt_parser.add_argument("--data-dir", type=Path, default=Path("hydrowatch_amur"))

    # подкоманда audit
    audit_parser = subparsers.add_parser("audit", help="Generate cryptographic Merkle audit certificate")
    audit_parser.add_argument("--pair-id", type=str, required=True, help="Pair ID to audit")
    audit_parser.add_argument("--output-json", type=Path, default=None, help="Path to save audit certificate JSON")

    # подкоманда uncertainty
    unc_parser = subparsers.add_parser("uncertainty", help="Compute spatial error bounds and confidence interval")
    unc_parser.add_argument("--pair-id", type=str, required=True, help="Pair ID for uncertainty estimation")
    unc_parser.add_argument(
        "--confidence-level", type=float, default=0.95, help="Statistical confidence level (default 0.95)"
    )
    unc_parser.add_argument(
        "--spatial-correlation", type=float, default=0.20, help="Spatial autocorrelation coefficient rho (default 0.20)"
    )
    unc_parser.add_argument("--output-json", type=Path, default=None, help="Path to save uncertainty results JSON")

    # подкоманда manifest
    manifest_parser = subparsers.add_parser(
        "manifest", help="Generate or verify SHA-256 integrity manifest for artifacts and MRV verification"
    )
    manifest_parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("data/artifacts_manifest.json"),
        help="Path to manifest JSON file (default: data/artifacts_manifest.json)",
    )
    manifest_parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify existing manifest against disk artifacts",
    )
    manifest_parser.add_argument(
        "--base-dir",
        type=Path,
        default=Path("."),
        help="Base directory for artifact paths (default: .)",
    )
    manifest_parser.add_argument(
        "--targets",
        nargs="*",
        default=None,
        help="Specific files or directories to include",
    )

    args, unknown = parser.parse_known_args()

    if args.command == "predict":
        if not check_s1_data_available(args.pairs, args.data_dir):
            print(DATA_DOWNLOAD_HINT, file=sys.stderr)
            sys.exit(1)
        sys.argv = [sys.argv[0]]
        if args.pairs:
            sys.argv.extend(["--pairs", str(args.pairs)])
        if args.data_dir:
            sys.argv.extend(["--data_dir", str(args.data_dir)])
        if args.output_csv:
            sys.argv.extend(["--output_csv", str(args.output_csv)])
        if args.predictions_dir:
            sys.argv.extend(["--predictions_dir", str(args.predictions_dir)])
        if args.ablation_mode:
            sys.argv.extend(["--ablation_mode", str(args.ablation_mode)])
        if args.workers is not None:
            sys.argv.extend(["--workers", str(args.workers)])
        predict_main()
    elif args.command == "evaluate":
        sys.argv = [sys.argv[0]]
        if args.pairs:
            sys.argv.extend(["--pairs", str(args.pairs)])
        if args.data_dir:
            sys.argv.extend(["--data_dir", str(args.data_dir)])
        if args.submission_csv:
            sys.argv.extend(["--submission", str(args.submission_csv)])
        if args.predictions_dir:
            sys.argv.extend(["--predictions_dir", str(args.predictions_dir)])
        if args.run_ablations:
            sys.argv.append("--run_ablations")
        if args.holdout:
            sys.argv.append("--holdout")
        evaluate_main()
    elif args.command == "report":
        run_report(pair_id=args.pair_id, output=args.output)
    elif args.command == "fetch":
        run_fetch(
            pairs_csv_path=args.pairs,
            data_dir=args.data_dir,
            archive_output=args.archive_output,
            keep_archive=not args.no_keep_archive,
        )
    elif args.command == "benchmark":
        run_benchmark(
            pairs_csv_path=args.pairs,
            data_dir=args.data_dir,
            predictions_dir=args.predictions_dir,
            iterations=args.iterations,
            output_json=args.output_json,
        )
    elif args.command == "fetch-optical":
        from scripts.fetch_real_s2 import fetch_optical_scenes

        fetch_optical_scenes(
            pairs_csv_path=args.pairs,
            data_dir=args.data_dir,
            pair_id=args.pair_id,
        )
    elif args.command == "audit":
        run_audit(pair_id=args.pair_id, output_json=args.output_json)
    elif args.command == "uncertainty":
        run_uncertainty(
            pair_id=args.pair_id,
            confidence_level=args.confidence_level,
            spatial_correlation=args.spatial_correlation,
            output_json=args.output_json,
        )
    elif args.command == "manifest":
        run_manifest(
            output_path=args.output,
            verify=args.verify,
            base_dir=args.base_dir,
            targets=args.targets,
        )


if __name__ == "__main__":
    main()
