def get_cpu_data() -> list[int]:
    with open('/proc/stat', 'r', encoding='utf-8') as f:
        line = f.readline()
    
    cleaned: list[str] = line.split()
    return [int(item) for item in cleaned[1:]]

def calculate() -> dict[str, int]:
    cpu_times: list[int] = get_cpu_data()
    total_time = sum(cpu_times)
    
    idle_time = cpu_times[3]
    iowait_time = cpu_times[4]
    
    total_idle = idle_time + iowait_time
    
    return {
        "total": total_time,
        "idle_only": idle_time,
        "idle_plus_iowait": total_idle
    }
