import soundcard as sc
import numpy as np
import threading
import time

class DualStreamRouter:
    def __init__(self):
        self.is_running = False
        self.target_devices = {}
        self.silence_threshold = 0.0005 # Optimized for absolutely zero static
        self.threads = []

    def get_loopback_mic(self):
        """Find the system loopback channel to capture internal audio securely."""
        try:
            speaker = sc.default_speaker()
            mics = sc.all_microphones(include_loopback=True)
            for m in mics:
                if speaker.name in m.name:
                    return m
        except Exception:
            pass
        return None

    def calculate_auto_delay(self, device_name):
        name_lower = device_name.lower()
        if any(keyword in name_lower for keyword in ["bluetooth", "hands-free", "bose", "sony", "boat", "airpods", "wireless"]):
            return 150 
        elif "usb" in name_lower:
            return 40
        else:
            return 0

    def play_stream(self, speaker, loopback_mic, volume_multiplier, manual_delay_ms, device_name):
        auto_delay_ms = self.calculate_auto_delay(device_name)
        total_delay_ms = auto_delay_ms + manual_delay_ms
        
        if total_delay_ms > 0:
            time.sleep(total_delay_ms / 1000.0)

        try:
            # Added blocksize to prevent buffer underruns and irritating static sounds
            with loopback_mic.recorder(samplerate=44100, blocksize=1024) as mic, \
                 speaker.player(samplerate=44100, blocksize=1024) as sp:
                
                while self.is_running:
                    data = mic.record(numframes=1024)
                    
                    processed_data = data * volume_multiplier
                    volume_level = np.linalg.norm(processed_data)
                    
                    # Strict Silence Injector to prevent connection drops & buzzing
                    if volume_level < self.silence_threshold:
                        zero_data = np.zeros_like(processed_data)
                        sp.play(zero_data)
                    else:
                        sp.play(processed_data)
        except Exception as e:
            print(f"[{device_name}] Stream interrupted or disconnected cleanly. ({e})")

    def start_routing(self, device_settings):
        self.is_running = True
        loopback_mic = self.get_loopback_mic()
        
        if not loopback_mic:
            return False

        all_speakers = sc.all_speakers()
        
        for sp in all_speakers:
            if sp.name in device_settings:
                settings = device_settings[sp.name]
                self.target_devices[sp.name] = {
                    'speaker': sp,
                    'volume': settings.get('volume', 1.0),
                    'manual_delay_ms': settings.get('delay_ms', 0)
                }

        for name, config in self.target_devices.items():
            t = threading.Thread(
                target=self.play_stream, 
                args=(config['speaker'], loopback_mic, config['volume'], config['manual_delay_ms'], name)
            )
            t.daemon = True
            t.start()
            self.threads.append(t)
            
        return True

    def stop_routing(self):
        self.is_running = False
        for t in self.threads:
            t.join(timeout=1.0)
        self.threads.clear()
        self.target_devices.clear()