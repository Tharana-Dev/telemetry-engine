import time
import tracemalloc
import inspect
import platform

# --- DYNAMIC IMPORTS BASED ON OS ---
sys_type = platform.system()

if sys_type == "Linux":
    from engine.linux_sampler import LinuxCollector
    from engine.linux_thermal import LinuxThermalSampler
    collector = LinuxCollector()
    thermal_collector = LinuxThermalSampler()
else:
    from engine.universal_sampler import PsutilCollector
    from engine.universal_impl.universal_thermal import UniversalThermalSampler
    collector = PsutilCollector()
    thermal_collector = UniversalThermalSampler()


def benchmark_collector_method(method_to_run, total_runs=10, iterations_per_run=100):
    """
    Benchmarks any collector method and returns metrics for every run 
    plus overall statistics.
    """
    all_runs_timings = []
    per_run_stats = []

    for run in range(1, total_runs + 1):
        run_timings = []
        
        for _ in range(iterations_per_run):
            t1 = time.perf_counter_ns()
            method_to_run()
            t2 = time.perf_counter_ns()
            
            time_ms = (t2 - t1) / 1_000_000
            run_timings.append(time_ms)
        
        all_runs_timings.append(run_timings)
        per_run_stats.append({
            "run": run,
            "min": min(run_timings),
            "max": max(run_timings),
            "avg": sum(run_timings) / len(run_timings)
        })
    flattened_timings = [t for run in all_runs_timings for t in run]
    
    overall_stats = {
        "min": min(flattened_timings),
        "max": max(flattened_timings),
        "avg": sum(flattened_timings) / len(flattened_timings)
    }
    
    return {
        "per_run": per_run_stats,
        "overall": overall_stats
    }


methods = []

for name, func in inspect.getmembers(collector, predicate=inspect.ismethod):
    # Filter out private methods and the specific thermal snapshot method
    if not name.startswith("_") and name != "get_thermal_snapshot":
        methods.append((name, func))

TARGET_LIMIT_MS = 3.8
OUTPUT_FILE = f"optimization_results_{sys_type.lower()}.txt"

print(f"Starting benchmark... Results will be saved to {OUTPUT_FILE}")

# Open the file once and write everything to it
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    
    for method_name, method_func in methods:
        f.write(f"\n========================================\n")
        f.write(f"AUTOMATED BENCHMARK FOR: {method_name}\n")
        f.write(f"========================================\n")
        
        # 1. TIME BENCHMARK
        time_results = benchmark_collector_method(method_func, total_runs=10, iterations_per_run=100)
        
        for run_data in time_results['per_run']:
            f.write(f"Time - Run {run_data['run']} - Min: {run_data['min']:.4f} ms, Max: {run_data['max']:.4f} ms, Avg: {run_data['avg']:.4f} ms\n")
        
        overall = time_results['overall']
        f.write(f"Time - Overall - Min: {overall['min']:.4f} ms, Max: {overall['max']:.4f} ms, Avg: {overall['avg']:.4f} ms\n")
        
        # 2. PERFORMANCE EVALUATION (TARGET < 3.8 ms)
        actual_avg = overall['avg']
        if actual_avg < TARGET_LIMIT_MS:
            status = "PASS"
            factor = TARGET_LIMIT_MS / max(actual_avg, 0.000001)
            f.write(f"Evaluation: {status} ({factor:.2f}x FASTER than target of {TARGET_LIMIT_MS} ms)\n")
        else:
            status = "FAIL"
            factor = actual_avg / TARGET_LIMIT_MS
            f.write(f"Evaluation: {status} ({factor:.2f}x SLOWER than target of {TARGET_LIMIT_MS} ms)\n")
        
        # 3. MEMORY BENCHMARK
        tracemalloc.start()
        for _ in range(1000):
            method_func()
        snap = tracemalloc.take_snapshot()
        tracemalloc.stop()
        
        top_stats = snap.statistics('lineno')
        f.write(f"\nTop Memory Allocations for {method_name}:\n")
        for index, stat in enumerate(top_stats[:5], start=1):
            f.write(f"  #{index}: {stat}\n")


    # --- ISOLATED THERMAL BENCHMARK ---
    f.write(f"\n========================================\n")
    f.write(f"AUTOMATED BENCHMARK FOR: get_thermal_snapshot ({sys_type})\n")
    f.write(f"========================================\n")

    THERMAL_TARGET_LIMIT_MS = 1000.0  # 1 second target

    thermal_results = benchmark_collector_method(
        thermal_collector.get_thermal_snapshot, 
        total_runs=3, 
        iterations_per_run=5
    )

    for run_data in thermal_results['per_run']:
        f.write(f"Time - Run {run_data['run']} - Min: {run_data['min']:.4f} ms, Max: {run_data['max']:.4f} ms, Avg: {run_data['avg']:.4f} ms\n")

    thermal_overall = thermal_results['overall']
    f.write(f"Time - Overall - Min: {thermal_overall['min']:.4f} ms, Max: {thermal_overall['max']:.4f} ms, Avg: {thermal_overall['avg']:.4f} ms\n")

    actual_thermal_avg = thermal_overall['avg']
    if actual_thermal_avg < THERMAL_TARGET_LIMIT_MS:
        status = "PASS"
        factor = THERMAL_TARGET_LIMIT_MS / max(actual_thermal_avg, 0.000001)
        f.write(f"Evaluation: {status} ({factor:.2f}x FASTER than target of {THERMAL_TARGET_LIMIT_MS} ms)\n")
    else:
        status = "FAIL"
        factor = actual_thermal_avg / THERMAL_TARGET_LIMIT_MS
        f.write(f"Evaluation: {status} ({factor:.2f}x SLOWER than target of {THERMAL_TARGET_LIMIT_MS} ms)\n")

    tracemalloc.start()
    for _ in range(50):
        thermal_collector.get_thermal_snapshot()
    thermal_snap = tracemalloc.take_snapshot()
    tracemalloc.stop()

    top_thermal_stats = thermal_snap.statistics('lineno')
    f.write(f"\nTop Memory Allocations for get_thermal_snapshot:\n")
    for index, stat in enumerate(top_thermal_stats[:5], start=1):
        f.write(f"  #{index}: {stat}\n")

print(f"Benchmark complete. Open {OUTPUT_FILE} to view the results.")