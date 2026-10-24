import os
import time
from engine.linux_memory import LinuxMemorySampler
from engine.linux_cpu import LinuxCpuSampler

def main():
    memory_sampler = LinuxMemorySampler()
    cpu_sampler = LinuxCpuSampler()
    
    try:
        while True:
            os.system('clear')
            
            mem_snapshot = memory_sampler.get_snapshot()
            cpu_snapshot = cpu_sampler.get_snapshot()
            
            print("====================================")
            print("      SYSTEM TELEMETRY ENGINE       ")
            print("====================================")
            print(f"CPU Usage:                {cpu_snapshot.usage_pct}%")
            print("------------------------------------")
            print(f"Total Memory:             {round(mem_snapshot.total_gb, 2)} GB")
            print(f"Used Memory:              {round(mem_snapshot.used_gb, 2)} GB")
            print(f"Available Memory:         {round(mem_snapshot.available_gb, 2)} GB")
            print(f"Memory Usage Percentage:  {round(mem_snapshot.used_pct, 2)}%")
            print("====================================")
            print("Press Ctrl+C to exit.")
            
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nTelemetry engine shut down safely. Goodbye!")

if __name__ == "__main__":
    main()
