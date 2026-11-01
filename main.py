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
            # --- Gather fresh snapshots (each isolated) ---
            try:
                cpu = data.get_cpu_snapshot()
                cpu_error = None
            except Exception as e:
                cpu = None
                cpu_error = str(e)

            try:
                memory = data.get_memory_snapshot()
                memory_error = None
            except Exception as e:
                memory = None
                memory_error = str(e)

            try:
                battery = data.get_battery_snapshot()
                battery_error = None
            except Exception as e:
                battery = None
                battery_error = str(e)

            try:
                thermal = data.get_thermal_snapshot()
                thermal_error = None
            except Exception as e:
                thermal = None
                thermal_error = str(e)

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
            if cpu is None:
                print(f"CPU Usage:                Unavailable ({cpu_error})")
            else:
                print(f"CPU Usage:                {cpu.usage_pct}%") 
            print("------------------------------------") 

            if memory is None:
                print(f"Memory:                   Unavailable ({memory_error})")
            else:
                print(f"Total Memory:             {round(memory.total_gb, 2)} GB") 
                print(f"Used Memory:              {round(memory.used_gb, 2)} GB") 
                print(f"Available Memory:         {round(memory.available_gb, 2)} GB") 
                print(f"Memory Usage Percentage:  {round(memory.used_pct, 2)}%") 
            
            # --- BATTERY TELEMETRY BLOCK ---
            print("====================================")
            print("         BATTERY TELEMETRY          ")
            print("====================================")
            
            if battery_error is not None:
                print(f"Battery:                  Unavailable ({battery_error})")
            elif battery is None:
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

            if thermal is None:
                print(f"Thermal:                  Unavailable ({thermal_error})")
            else:
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

                # --- UPDATED: MULTI-GPU RENDER ENGINE (attribute access) ---
                if thermal.gpu_available:
                    if thermal.gpus:
                        for gpu in thermal.gpus:
                            g_name = gpu.name
                            g_temp = gpu.temperature_c
                            g_util = gpu.utilization_pct
                            g_watt = gpu.power_w
                            g_fan  = gpu.fan_speed_pct

                            temp_str = f"{g_temp}°C" if g_temp is not None else "N/A"
                            util_str = f"{g_util}%" if g_util is not None else "N/A"
                            watt_str = f"{g_watt} W" if g_watt is not None else "N/A"
                            fan_str  = f"{g_fan}%"  if g_fan  is not None else "N/A (EC Owned)"

                            print(f"GPU [{gpu.index}]:                 {g_name}")
                            print(f"  Temp / Util:            {temp_str} / {util_str}")
                            print(f"  Power Draw:             {watt_str}")
                            print(f"  Fan Speed:              {fan_str}")
                    else:
                        # Fallback UI layout using the __post_init__ auto-mapped parent attributes
                        print(f"GPU Temp:                 {thermal.gpu_temp if thermal.gpu_temp is not None else 'N/A'}")
                        print(f"GPU Fan:                  {thermal.gpu_fan if thermal.gpu_fan is not None else 'N/A'}")
                        print(f"GPU Usage:                {thermal.gpu_usage if thermal.gpu_usage is not None else 'N/A'}")
                        print(f"GPU Power:                {thermal.gpu_power_watts if thermal.gpu_power_watts is not None else 'N/A'}")
                else:
                    print(f"GPU Status:               {thermal.gpu_error}. Check If you are using ECO mode.")
                
            print("====================================") 
            print("\nPress Ctrl+C to exit.")
            
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nProgram interrupted. Exiting gracefully.")

if __name__ == "__main__":
    main()