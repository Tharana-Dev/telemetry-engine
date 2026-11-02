import os
import time
from engine.linux_sampler import LinuxCollector
from engine.psutil_sampler import PsutilCollector
import platform

def format_speed_bits(bytes_per_second):
    """Converts bytes/sec to bits/sec and formats as industry-standard Kbps or Mbps."""
    bits_per_second = bytes_per_second * 8
    kbps = bits_per_second / 1000  # Networking standard uses base-1000 for bits

    if kbps < 1000:
        return f"{kbps:.2f} Kbps"
    else:
        mbps = kbps / 1000
        return f"{mbps:.2f} Mbps"

def format_total_data(total_bytes):
    """Converts total cumulative bytes into binary human-readable strings (KB, MB, GB)."""
    for unit in ['Bytes', 'KB', 'MB', 'GB', 'TB']:
        if total_bytes < 1024.0:
            return f"{total_bytes:.2f} {unit}"
        total_bytes /= 1024.0
    return f"{total_bytes:.2f} PB"


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

            try:
                disk_io = data.get_disk_io_snapshot()
                disk_io_error = None
            except Exception as e:
                disk_io = None
                disk_io_error = str(e)

            try:
                disk_space = data.get_disk_space_snapshot()
                disk_space_error = None
            except Exception as e:
                disk_space = None
                disk_space_error = str(e)
            
            try:
                network_data = data.get_network_snapshot()
                network_error = None
            except Exception as e:
                network_data = None
                network_error = str(e)

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
                        print(f"GPU Temp:                 {thermal.gpu_temp if thermal.gpu_temp is not None else 'N/A'}")
                        print(f"GPU Fan:                  {thermal.gpu_fan if thermal.gpu_fan is not None else 'N/A'}")
                        print(f"GPU Usage:                {thermal.gpu_usage if thermal.gpu_usage is not None else 'N/A'}")
                        print(f"GPU Power:                {thermal.gpu_power_watts if thermal.gpu_power_watts is not None else 'N/A'}")
                else:
                    print(f"GPU Status:               {thermal.gpu_error}. Check If you are using ECO mode.")
                
            # --- DISK TELEMETRY BLOCK ---
            print("====================================")
            print("          DISK TELEMETRY            ")
            print("====================================")

            if disk_space_error is not None:
                print(f"Disk Space:               Unavailable ({disk_space_error})")
            elif disk_space is not None:
                print(f"Total Space:              {disk_space.total_gb} GB")
                print(f"Used Space:               {disk_space.used_gb} GB")
                print(f"Free Space:               {disk_space.free_gb} GB")
                print(f"Disk Usage Percentage:    {disk_space.percent}%")
            
            print("------------------------------------")

            if disk_io_error is not None:
                print(f"Disk I/O:                 Unavailable ({disk_io_error})")
            elif disk_io is not None:
                if not disk_io:
                    print("Disk I/O:                 Initializing... (Requires 1s delta)")
                else:
                    for io in disk_io:
                        print(f"{io.device}:")
                        print(f"  Read Speed:             {io.read_mbps} MB/s")
                        print(f"  Write Speed:            {io.write_mbps} MB/s")


            print("====================================")
            print("         NETWORK TELEMETRY          ")
            print("====================================")

            if network_error is not None:
                print(f"Network Telemetry:        Unavailable ({network_error})")
            elif network_data is not None:
                if not network_data:
                    print("Network Telemetry:        Initializing... (Requires 1s delta)")
                else:
                    for item in network_data:
                        print(f"{item.interface}:")
                        print(f"  Status:                 {item.status}")

                        if item.status == "CONNECTED":
                            print(f"  Download Speed:         {format_speed_bits(item.download_mbps)}")
                            print(f"  Upload Speed:           {format_speed_bits(item.upload_mbps)}")
                            print(f"  Rx Errors/Drops:        {item.rx_errors}/{item.rx_drops}")
                            print(f"  Tx Errors/Drops:        {item.tx_errors}/{item.tx_drops}")
                            print(f"  Total Transferred:      {format_total_data(item.total_gb)}")
                        elif item.status == "CONNECTING":
                            print("  Network Activity:       Initializing new interface link...")
                            print(f"  Total Historical Data:  {format_total_data(item.total_gb)}")
                        else:
                            print("  Network Activity:       Offline / Unplugged")
                
            print("====================================") 
            print("\nPress Ctrl+C to exit.")
            
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nProgram interrupted. Exiting gracefully.")

if __name__ == "__main__":
    main()