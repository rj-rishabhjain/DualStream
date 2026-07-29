import soundcard as sc

def list_available_devices():
    print("Scanning for Output Devices...\n")
    
    speakers = sc.all_speakers()
    
    if not speakers:
        print("No audio devices found! Please check your system settings.")
        return

    print("--- Available Output Devices in Dual Stream ---")
    for index, speaker in enumerate(speakers):
        print(f"[{index}] {speaker.name}")
        
    print("\nScan Complete. Foundation is solid!")

if __name__ == "__main__":
    list_available_devices()