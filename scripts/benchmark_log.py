from datetime import datetime


def render_benchmark_entry(
    title: str,
    metadata: dict[str, str],
    cases: dict[str, dict[str, dict[str, float] | dict[str, float]]],
    notes: list[str] | None = None,
) -> str:
    lines = [f"## {title}", ""]

    for label, value in metadata.items():
        pretty_label = label.replace("_", " ").capitalize()
        lines.append(f"- {pretty_label}: `{value}`")

    for case_name, summary in cases.items():
        lines.extend(["", f"### {case_name}", ""])
        round_trip = summary.get("round_trip_ms", {})
        api_latency = summary.get("api_latency_ms", {})
        stage_timings = summary.get("stage_timings_ms", {})
        if round_trip:
            lines.append(f"- Round-trip mean: {round_trip['mean']:.2f} ms")
            lines.append(f"- Round-trip p50: {round_trip['p50']:.2f} ms")
            lines.append(f"- Round-trip p95: {round_trip['p95']:.2f} ms")
            lines.append(f"- Round-trip max: {round_trip['max']:.2f} ms")
        if api_latency:
            lines.append(f"- API latency mean: {api_latency['mean']:.2f} ms")
            lines.append(f"- API latency p50: {api_latency['p50']:.2f} ms")
            lines.append(f"- API latency p95: {api_latency['p95']:.2f} ms")
            lines.append(f"- API latency max: {api_latency['max']:.2f} ms")
        if stage_timings:
            lines.append("- Average stage timings:")
            for stage_name, value in stage_timings.items():
                lines.append(f"- `{stage_name}`: {value:.2f} ms")

    if notes:
        lines.extend(["", "### Notes", ""])
        for note in notes:
            lines.append(f"- {note}")

    return "\n".join(lines).strip() + "\n"


def benchmark_metadata(
    *,
    commit: str,
    environment: str,
    command: str,
    date: str | None = None,
) -> dict[str, str]:
    return {
        "date": date or datetime.utcnow().date().isoformat(),
        "commit": commit,
        "environment": environment,
        "command": command,
    }
