import argparse
from datetime import datetime, timezone

from scripts.benchmark_predict import build_case_plan, run_case_benchmark, summarize_case_results


def main():
    parser = argparse.ArgumentParser(description="Run live-server /predict benchmarks.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--iterations", type=int, default=50)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--scenario", choices=["warm", "cold", "mixed-80-20"], default="mixed-80-20")
    parser.add_argument("--time", dest="timestamp", default=datetime.now(timezone.utc).isoformat())
    args = parser.parse_args()

    case_plan = build_case_plan(args.iterations, args.scenario)
    results = run_case_benchmark(
        base_url=args.base_url,
        timestamp=args.timestamp,
        concurrency=args.concurrency,
        case_plan=case_plan,
        symbol_for_case={"warm": "MOCKWARM", "cold": "MOCKCOLD"},
    )
    summary = summarize_case_results(results)

    print(f"iterations={args.iterations}")
    print(f"concurrency={args.concurrency}")
    print(f"scenario={args.scenario}")
    for case_name, case_summary in summary.items():
        print(f"[{case_name}]")
        for metric_name, values in case_summary.items():
            if metric_name == "stage_timings_ms":
                continue
            print(f"{metric_name}_mean_ms={values['mean']:.2f}")
            print(f"{metric_name}_p50_ms={values['p50']:.2f}")
            print(f"{metric_name}_p95_ms={values['p95']:.2f}")
            print(f"{metric_name}_max_ms={values['max']:.2f}")
        for stage_name, value in case_summary["stage_timings_ms"].items():
            print(f"stage_{stage_name}_mean_ms={value:.2f}")


if __name__ == "__main__":
    main()
