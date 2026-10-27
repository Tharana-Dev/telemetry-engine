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
            # Gather fresh snapshots
            memory = data.get_memory_snapshot()
            battery = data.get_battery_snapshot()
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
                
            # --- CPU & MEMORY BLOCKS ---
            print(f"CPU Usage:                {data.get_cpu_snapshot().usage_pct}%") 
            print("------------------------------------") 
            print(f"Total Memory:             {round(memory.total_gb, 2)} GB") 
            print(f"Used Memory:              {round(memory.used_gb, 2)} GB") 
            print(f"Available Memory:         {round(memory.available_gb, 2)} GB") 
            print(f"Memory Usage Percentage:  {round(memory.used_pct, 2)}%") 
            
            # --- BATTERY TELEMETRY BLOCK ---
            print("====================================")
            print("         BATTERY TELEMETRY          ")
            print("====================================")
            
            if battery is None:
                print("Battery:                  Not Detected (Desktop/Server)")
            else:
                # Interrogate status string & format remaining time nicely
                if battery.status == "Discharging" and battery.hours_left > 0:
                    hours = int(battery.hours_left)
                    minutes = int((battery.hours_left - hours) * 60)
                    time_str = f"{hours}h {minutes}m remaining"
                elif battery.status in ("Charging", "Full", "Not charging") or battery.online:
                    time_str = "Wall Power (AC)"
                else:
                    time_str = "Calculating..."

                # Interrogate health percentage
                # Using -1 or 0 to track unsupported values on cross-platform fallbacks
                if battery.health_percent <= 0 or (fallback_active and battery.health_percent == 100.0):
                    health_str = "N/A (OS Wrapper Restriction)"
                else:
                    health_str = f"{battery.health_percent:.1f}%"

                # Interrogate draw/wattage values
                if battery.power_watts <= 0:
                    draw_str = "N/A (OS Wrapper Restriction)"
                else:
                    draw_str = f"{battery.power_watts:.3f} W"

                print(f"Status:                   {battery.status}")
                print(f"Capacity:                 {battery.capacity}%")
                print(f"Power Draw:               {draw_str}")
                print(f"Time Estimate:            {time_str}")
                print(f"Battery Health:           {health_str}")
                
            print("====================================") 
            print("\nPress Ctrl+C to exit.")
            
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nProgram interrupted. Exiting gracefully.")

if __name__ == "__main__":
    main()
