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
            thermal = data.get_thermal_snapshot()  # Contains the updated .gpus multi-GPU array
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
                if battery.status == "Discharging" and battery.hours_left > 0:
                    hours = int(battery.hours_left)
                    minutes = int((battery.hours_left - hours) * 60)
                    time_str = f"{hours}h {minutes}m remaining"
                elif battery.status in ("Charging", "Full", "Not charging") or battery.online:
                    time_str = "Wall Power (AC)"
                else:
                    time_str = "Calculating..."

                if battery.health_percent <= 0 or (fallback_active and battery.health_percent == 100.0):
                    health_str = "N/A (OS Wrapper Restriction)"
                else:
                    health_str = f"{battery.health_percent:.1f}%"

                if battery.power_watts <= 0:
                    draw_str = "N/A (OS Wrapper Restriction)"
                else:
                    draw_str = f"{battery.power_watts:.3f} W"

                print(f"Status:                   {battery.status}")
                print(f"Capacity:                 {battery.capacity}%")
                print(f"Power Draw:               {draw_str}")
                print(f"Time Estimate:            {time_str}")
                print(f"Battery Health:           {health_str}")

            # --- THERMAL TELEMETRY BLOCK ---
            print("====================================")
            print("         THERMAL TELEMETRY          ")
            print("====================================")

            if thermal.sensor_available:
                print(f"CPU Vendor:               {thermal.cpu_vendor}")
                print(f"Motherboard:              {thermal.board_vendor}")
                
                cpu_t = f"{thermal.cpu_temp}°C" if thermal.cpu_temp is not None else "N/A"
                cpu_m = f"{thermal.cpu_temp_max}°C" if thermal.cpu_temp_max is not None else "N/A"
                print(f"CPU Temp:                 {cpu_t} (Max: {cpu_m})")
                
                if thermal.system_fans:
                    for fan, rpm in thermal.system_fans.items():
                        print(f"{fan.capitalize()}:                  {rpm} RPM")
                else:
                    print("System Fans:              N/A")
            else:
                print(f"Sensor Error:             {thermal.sensor_error}")

            # --- UPDATED: MULTI-GPU RENDER ENGINE ---
            if thermal.gpu_available:
                if thermal.gpus:
                    for gpu in thermal.gpus:
                        # Extract metrics safely from dictionary maps
                        g_name = gpu.get("name", "Unknown GPU")
                        g_temp = gpu.get("temperature_c")
                        g_util = gpu.get("utilization_pct")
                        g_watt = gpu.get("power_w")
                        g_fan  = gpu.get("fan_speed_pct")
                        
                        fan_str = f"{g_fan}%" if g_fan is not None else "N/A (EC Owned)"
                        
                        print(f"GPU [{gpu.get('index', 0)}]:                 {g_name}")
                        print(f"  Temp / Util:            {g_temp}°C / {g_util}%")
                        print(f"  Power Draw:             {g_watt} W")
                        print(f"  Fan Speed:              {fan_str}")
                else:
                    # Fallback UI layout using the __post_init__ auto-mapped parent attributes
                    print(f"GPU Temp:                 {thermal.gpu_temp}°C")
                    print(f"GPU Fan:                  {thermal.gpu_fan if thermal.gpu_fan is not None else 'N/A'}")
                    print(f"GPU Usage:                {thermal.gpu_usage}%")
                    print(f"GPU Power:                {thermal.gpu_power_watts} W")
            else:
                print(f"GPU Status:               {thermal.gpu_error}")
                
            print("====================================") 
            print("\nPress Ctrl+C to exit.")
            
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nProgram interrupted. Exiting gracefully.")

if __name__ == "__main__":
    main()
