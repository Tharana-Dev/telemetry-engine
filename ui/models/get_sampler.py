import platform

def get_sampler():
    if platform.system() == "Windows":
        from engine.universal_sampler import PsutilCollector
        return PsutilCollector()
    else:
        from engine.linux_sampler import LinuxCollector
        return LinuxCollector()