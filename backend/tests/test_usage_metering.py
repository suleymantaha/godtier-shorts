from decimal import Decimal

from backend.core.usage_metering import UsageMeter


def test_usage_meter_records_stage_durations_outputs_retries_and_cost() -> None:
    ticks = iter([10.0, 12.0, 14.0, 19.0, 25.0])
    meter = UsageMeter(
        source_seconds=600,
        retry_count=2,
        gpu_hourly_cost_usd=Decimal("0.90"),
        clock=lambda: next(ticks),
    )

    meter.start_stage("transcript")
    meter.start_stage("tracking")
    meter.start_stage("render")
    snapshot = meter.finish(gpu_model="RTX Test", peak_vram_mb=1024, output_count=3)

    assert snapshot.source_seconds == 600
    assert snapshot.transcript_seconds == 2
    assert snapshot.tracking_seconds == 5
    assert snapshot.render_seconds == 6
    assert snapshot.total_wall_seconds == 15
    assert snapshot.gpu_seconds == 15
    assert snapshot.output_count == 3
    assert snapshot.retry_count == 2
    assert snapshot.estimated_internal_cost_usd == Decimal("0.003750")


def test_usage_meter_maps_worker_progress_to_stages() -> None:
    ticks = iter([0.0, 1.0, 3.0, 6.0, 10.0])
    meter = UsageMeter(source_seconds=30, clock=lambda: next(ticks))

    meter.observe(20, "transcription")
    meter.observe(55, "person tracking")
    meter.observe(80, "rendering")
    snapshot = meter.finish(gpu_model="L40S", output_count=1)

    assert snapshot.transcript_seconds == 2
    assert snapshot.tracking_seconds == 3
    assert snapshot.render_seconds == 4
