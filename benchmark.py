import time
import tracemalloc
from engine.linux_sampler import LinuxCollector
from engine.linux_thermal import LinuxThermalSampler
import inspect


collector = LinuxCollector()

import time

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

# 2. Run the benchmarks for each discovered method
TARGET_LIMIT_MS = 3.8

# Run the benchmarks for each discovered method
for method_name, method_func in methods:
    print(f"\n========================================")
    print(f"AUTOMATED BENCHMARK FOR: {method_name}")
    print(f"========================================")
    
    # 1. TIME BENCHMARK
    time_results = benchmark_collector_method(method_func, total_runs=10, iterations_per_run=100)
    
    for run_data in time_results['per_run']:
        print(f"Time - Run {run_data['run']} - Min: {run_data['min']:.4f} ms, Max: {run_data['max']:.4f} ms, Avg: {run_data['avg']:.4f} ms")
    
    overall = time_results['overall']
    print(f"Time - Overall - Min: {overall['min']:.4f} ms, Max: {overall['max']:.4f} ms, Avg: {overall['avg']:.4f} ms")
    
    # 2. PERFORMANCE EVALUATION (TARGET < 3.8 ms)
    actual_avg = overall['avg']
    if actual_avg < TARGET_LIMIT_MS:
        status = "PASS"
        factor = TARGET_LIMIT_MS / max(actual_avg, 0.000001)
        print(f"Evaluation: {status} ({factor:.2f}x FASTER than target of {TARGET_LIMIT_MS} ms)")
    else:
        status = "FAIL"
        factor = actual_avg / TARGET_LIMIT_MS
        print(f"Evaluation: {status} ({factor:.2f}x SLOWER than target of {TARGET_LIMIT_MS} ms)")
    
    # 3. MEMORY BENCHMARK
    tracemalloc.start()
    
    for _ in range(10000):
        method_func()
        
    snap = tracemalloc.take_snapshot()
    tracemalloc.stop()
    
    top_stats = snap.statistics('lineno')
    print(f"\nTop Memory Allocations for {method_name}:")
    for index, stat in enumerate(top_stats[:5], start=1):
        print(f"  #{index}: {stat}")


#get_thermal_snapshots is ignored
#Because it spawns a subprocess (sensors -j) and initializes pynvml. 
# Running that 10,000 times would take minutes and grind your CPU to a halt. 
# Thermal is an external process, not a file read. 
# It needs to be benchmarked separately if at all.

#Testing Thermals in isolation
print(f"\n========================================")
print(f"AUTOMATED BENCHMARK FOR: get_thermal_snapshot")
print(f"========================================")

thermal_collector = LinuxThermalSampler()
THERMAL_TARGET_LIMIT_MS = 1000.0  # 1 second target

# --- TIME BENCHMARK (Reduced iterations due to subprocess overhead) ---
# We use 3 runs of 5 iterations to accommodate the slow external tools (sensors/pynvml)
thermal_results = benchmark_collector_method(
    thermal_collector.get_thermal_snapshot, 
    total_runs=3, 
    iterations_per_run=5
)

for run_data in thermal_results['per_run']:
    print(f"Time - Run {run_data['run']} - Min: {run_data['min']:.4f} ms, Max: {run_data['max']:.4f} ms, Avg: {run_data['avg']:.4f} ms")

thermal_overall = thermal_results['overall']
print(f"Time - Overall - Min: {thermal_overall['min']:.4f} ms, Max: {thermal_overall['max']:.4f} ms, Avg: {thermal_overall['avg']:.4f} ms")

# --- PERFORMANCE EVALUATION (TARGET < 1000 ms) ---
actual_thermal_avg = thermal_overall['avg']
if actual_thermal_avg < THERMAL_TARGET_LIMIT_MS:
    status = "PASS"
    factor = THERMAL_TARGET_LIMIT_MS / max(actual_thermal_avg, 0.000001)
    print(f"Evaluation: {status} ({factor:.2f}x FASTER than target of {THERMAL_TARGET_LIMIT_MS} ms)")
else:
    status = "FAIL"
    factor = actual_thermal_avg / THERMAL_TARGET_LIMIT_MS
    print(f"Evaluation: {status} ({factor:.2f}x SLOWER than target of {THERMAL_TARGET_LIMIT_MS} ms)")

# --- MEMORY BENCHMARK ---
tracemalloc.start()

# Reduced loop to 50 iterations since subprocesses are memory heavy at runtime
for _ in range(50):
    thermal_collector.get_thermal_snapshot()
    
thermal_snap = tracemalloc.take_snapshot()
tracemalloc.stop()

top_thermal_stats = thermal_snap.statistics('lineno')
print(f"\nTop Memory Allocations for get_thermal_snapshot:")
for index, stat in enumerate(top_thermal_stats[:5], start=1):
    print(f"  #{index}: {stat}")
