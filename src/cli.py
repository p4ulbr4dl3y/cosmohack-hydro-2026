"""CLI entry point for HydroWatch Amur."""

from __future__ import annotations

import argparse
import contextlib
import json
import logging
try:
    import resource
except ImportError:  # pragma: no cover
    resource = None
import sys
import time
from pathlib import Path

import pandas as pd

from src.data_fetch import DATA_URL, missing_s1_pairs, safe_extract
from src.evaluate import main as evaluate_main
from src.predict import main as predict_main
from src.predict import process_pair
from src.service.data_loader import DataLoader

logger = logging.getLogger(__name__)

#: Human-readable hint printed when Sentinel-1 scenes are missing (they are
#: distributed outside the git repository, see docs/Ссылка на данные.txt).
DATA_DOWNLOAD_HINT = """\
Sentinel-1 scenes are required to run prediction, but they are NOT in this
git repository (see .gitignore: hydrowatch_amur/rasters/**/S1_*.tif).

Fetch the full case dataset first:

    uv run python -m src.cli fetch

(Downloads the archive from Google Drive and unpacks it; requires no external
``unzip`` binary. The link is also documented in docs/Ссылка на данные.txt.)
After unpacking, hydrowatch_amur/rasters/ must contain the S1_pre_*.tif /
S1_peak_*.tif scenes referenced by hydrowatch_amur/pairs.csv.
"""


def run_report(pair_id: str | None = None, output: Path | None = None) -> None:
    """Generate summary report for one or all pairs."""
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
                        "natural_vegetation_ha": lc.get("natural_vegetation_ha", 0.0),
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
            print(
                f"  Natural flood: {lc.get('natural_vegetation_ha', 0.0):.2f} ha ({lc.get('natural_vegetation_pct', 0.0):.1f}%)"
            )
            print(f"  Mean HAND: {lc.get('mean_hand_m', 0.0):.2f} m")
        print("=" * 60)


def run_benchmark(
    pairs_csv_path: Path,
    data_dir: Path,
    predictions_dir: Path,
    iterations: int = 1,
) -> None:
    """Benchmark inference latency and memory throughput."""
    if not pairs_csv_path.exists():
        print(f"Error: pairs CSV not found at {pairs_csv_path}", file=sys.stderr)
        sys.exit(1)

    pairs_df = pd.read_csv(pairs_csv_path)
    total_pairs = len(pairs_df)
    times = []

    print(f"Benchmarking HydroWatch inference across {total_pairs} pairs ({iterations} iteration(s))...")
    tmp_out = predictions_dir / "_benchmark_tmp"
    tmp_out.mkdir(parents=True, exist_ok=True)

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

    # Clean up benchmark temp files
    for f in tmp_out.glob("*"):
        with contextlib.suppress(OSError):
            f.unlink()
    with contextlib.suppress(OSError):
        tmp_out.rmdir()

    avg_time = sum(times) / len(times)
    total_time = sum(times)
    fps = len(times) / total_time

    # Peak RSS: macOS returns bytes, Linux returns KiB, Windows fallback
    if resource is not None:
        ru_maxrss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        peak_mb = (ru_maxrss / (1024.0 * 1024.0)) if sys.platform == "darwin" else (ru_maxrss / 1024.0)
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


def check_s1_data_available(pairs_csv_path: Path, data_dir: Path) -> bool:
    """Return True when all S1 pre/peak scenes referenced by pairs.csv exist."""
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
    """Download the case dataset from Google Drive and unpack it."""
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

    # predict sub-command
    predict_parser = subparsers.add_parser(
        "predict", help="Run batch prediction on all pairs and generate submission.csv"
    )
    predict_parser.add_argument("--pairs", type=Path, default=Path("hydrowatch_amur/pairs.csv"))
    predict_parser.add_argument("--data-dir", type=Path, default=Path("hydrowatch_amur"))
    predict_parser.add_argument("--output-csv", type=Path, default=Path("submission.csv"))
    predict_parser.add_argument("--predictions-dir", type=Path, default=Path("predictions"))
    predict_parser.add_argument("--ablation-mode", type=int, default=4, choices=[1, 2, 3, 4])

    # evaluate sub-command
    eval_parser = subparsers.add_parser(
        "evaluate", help="Compute official score and raster metrics against reference masks"
    )
    eval_parser.add_argument("--pairs", type=Path, default=Path("hydrowatch_amur/pairs.csv"))
    eval_parser.add_argument("--data-dir", type=Path, default=Path("hydrowatch_amur"))
    eval_parser.add_argument("--submission-csv", type=Path, default=Path("submission.csv"))
    eval_parser.add_argument("--predictions-dir", type=Path, default=Path("predictions"))
    eval_parser.add_argument("--run-ablations", action="store_true", help="Run all 4 ablations")

    # report sub-command
    report_parser = subparsers.add_parser("report", help="Generate hydrological report for a pair or all pairs")
    report_parser.add_argument("--pair-id", type=str, default=None, help="Target pair identifier")
    report_parser.add_argument("--output", type=Path, default=None, help="Output file path (.json or .csv)")

    # fetch sub-command
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

    # benchmark sub-command
    bench_parser = subparsers.add_parser("benchmark", help="Benchmark pipeline latency and throughput")
    bench_parser.add_argument("--pairs", type=Path, default=Path("hydrowatch_amur/pairs.csv"))
    bench_parser.add_argument("--data-dir", type=Path, default=Path("hydrowatch_amur"))
    bench_parser.add_argument("--predictions-dir", type=Path, default=Path("predictions"))
    bench_parser.add_argument("--iterations", type=int, default=1, help="Number of benchmark iterations")

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
        )


if __name__ == "__main__":
    main()
