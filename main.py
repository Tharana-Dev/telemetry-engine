import os
import time
from engine.linux_sampler import LinuxCollector
from engine.psutil_sampler import PsutilCollector
import platform

def main():
    sys_type = platform.system()
    fallback_active = False
    fallback_reason = None
    
    # 1. Attempt to initialize the requested subsystem Engine
    if sys_type == "Linux":
        try:
            data = LinuxCollector()
        except (PermissionError, FileNotFoundError) as e:
            data = PsutilCollector()
            fallback_active = True
            fallback_reason = type(e).__name__
    else:
        data = PsutilCollector()
        
    clear_command = 'cls' if sys_type == "Windows" else 'clear'
    
    try:
        while True:
            memory = data.get_memory_snapshot()
            os.system(clear_command)
            
            print("====================================") 
            print("      SYSTEM TELEMETRY ENGINE       ") 
            print("====================================") 
            
            if fallback_active:
                print(f"[!] ENGINE FALLBACK ACTIVE ({fallback_reason})")
                print("[!] Using: psutil cross-platform core")
                print("------------------------------------")
            elif sys_type != "Linux":
                print(f"[*] ENGINE MODE: Native Cross-Platform ({sys_type})")
                print("------------------------------------")
            else:
                print("[*] ENGINE MODE: High-Performance Linux Native (/proc)")
                print("------------------------------------")
                
            print(f"CPU Usage:                {data.get_cpu_snapshot().usage_pct}%") 
            print("------------------------------------") 
            print(f"Total Memory:             {round(memory.total_gb, 2)} GB") 
            print(f"Used Memory:              {round(memory.used_gb, 2)} GB") 
            print(f"Available Memory:         {round(memory.available_gb, 2)} GB") 
            print(f"Memory Usage Percentage:  {round(memory.used_pct, 2)}%") 
            print("====================================") 
            print("\nPress Ctrl+C to exit.")
            
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nProgram interrupted. Exiting gracefully.")    
    
if __name__ == "__main__":
    main()
