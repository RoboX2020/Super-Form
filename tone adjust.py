# ====================================================================
# tone adjust.py - a small audio experiment (generates and tweaks tones).
# Parked in this repo, separate from the form filler.
# ====================================================================
import time
import numpy as np
import sounddevice as sd
import sys
import threading

# --- CONFIGURATION ---
SAMPLE_RATE = 44100

# --- AUDIO ENGINE ---
class GuitarEngine:
    def __init__(self):
        self.active_sounds = [] 
        self.lock = threading.Lock()
        
    def add_sound(self, sound_array):
        with self.lock:
            self.active_sounds.append([sound_array, 0])

    def callback(self, outdata, frames, time, status):
        if status: print(status, file=sys.stderr)
        mixed_audio = np.zeros(frames)
        with self.lock:
            for i in range(len(self.active_sounds) - 1, -1, -1):
                sound, idx = self.active_sounds[i]
                remaining = len(sound) - idx
                if remaining > frames:
                    mixed_audio += sound[idx : idx + frames]
                    self.active_sounds[i][1] += frames
                else:
                    mixed_audio[:remaining] += sound[idx:]
                    self.active_sounds.pop(i)
        
        # Smooth, singing tone (less distortion)
        mixed_audio = np.tanh(mixed_audio * 1.1) * 0.8
        outdata[:] = mixed_audio.reshape(-1, 1)

def generate_string_sound(freq, duration=2.5, decay=0.994):
    n_samples = int(duration * SAMPLE_RATE)
    N = int(SAMPLE_RATE / freq)
    buf = np.random.randn(N)
    samples = np.zeros(n_samples)
    for i in range(n_samples):
        samples[i] = buf[i % N]
        buf[i % N] = 0.5 * (buf[i % N] + buf[(i + 1) % N]) * decay
    return samples.astype(np.float32)

# --- FREQUENCIES ---
F4 = 349.23
G4 = 392.00
A4 = 440.00
B4 = 493.88
C5 = 523.25
D5 = 587.33
E5 = 659.25

# --- YOUR SEQUENCE ---
# I assigned durations (dur) to match the rhythm of the words
MELODY = [
    # --- LINE 1: "Har ghadi badal rahi hai roop zindagi" ---
    # Notes: C5, B4, C5, B4, C5, B4, C5, E5, D5, C5, B4, A4, B4, A4, B4, A4, A4
    {"note": "Har (C5)", "freq": C5, "dur": 0.25},
    {"note": "Gha (B4)", "freq": B4, "dur": 0.25},
    {"note": "di (C5)",  "freq": C5, "dur": 0.25},
    {"note": "Ba (B4)",  "freq": B4, "dur": 0.25},
    {"note": "dal (C5)", "freq": C5, "dur": 0.25},
    {"note": "Ra (B4)",  "freq": B4, "dur": 0.25},
    {"note": "hi (C5)",  "freq": C5, "dur": 0.25},
    
    {"note": "Hai (E5)", "freq": E5, "dur": 0.4}, # Higher pitch, slight hold
    {"note": "Roop (D5)","freq": D5, "dur": 0.3},
    {"note": "Zin (C5)", "freq": C5, "dur": 0.3},
    {"note": "da (B4)",  "freq": B4, "dur": 0.3},
    
    # The Trill at the end of line 1
    {"note": "gi (A4)",  "freq": A4, "dur": 0.2},
    {"note": "i (B4)",   "freq": B4, "dur": 0.2},
    {"note": "i (A4)",   "freq": A4, "dur": 0.2},
    {"note": "i (B4)",   "freq": B4, "dur": 0.2},
    {"note": "i (A4)",   "freq": A4, "dur": 0.4}, 
    {"note": "i (A4)",   "freq": A4, "dur": 0.8}, # End of line pause

    # --- LINE 2: "Chhaav hai kabhi, kabhi hai dhoop zindagi" ---
    # Notes: C5, B4, C5, B4, C5, B4, C5, E5, D5, C5, B4, A4, B4, A4, B4, A4, A4, A4
    {"note": "Chhaav (C5)", "freq": C5, "dur": 0.3},
    {"note": "hai (B4)",    "freq": B4, "dur": 0.3},
    {"note": "Ka (C5)",     "freq": C5, "dur": 0.25},
    {"note": "bhi (B4)",    "freq": B4, "dur": 0.25},
    {"note": "Ka (C5)",     "freq": C5, "dur": 0.25},
    {"note": "bhi (B4)",    "freq": B4, "dur": 0.25},
    {"note": "Hai (C5)",    "freq": C5, "dur": 0.3},
    
    {"note": "Dhoop (E5)",  "freq": E5, "dur": 0.4},
    {"note": "Zin (D5)",    "freq": D5, "dur": 0.3},
    {"note": "da (C5)",     "freq": C5, "dur": 0.3},
    {"note": "gi (B4)",     "freq": B4, "dur": 0.3},
    
    # The Trill at the end of line 2
    {"note": "i (A4)",   "freq": A4, "dur": 0.2},
    {"note": "i (B4)",   "freq": B4, "dur": 0.2},
    {"note": "i (A4)",   "freq": A4, "dur": 0.2},
    {"note": "i (B4)",   "freq": B4, "dur": 0.2},
    {"note": "i (A4)",   "freq": A4, "dur": 0.4},
    {"note": "i (A4)",   "freq": A4, "dur": 0.4},
    {"note": "i (A4)",   "freq": A4, "dur": 0.8}, # End of line pause

    # --- LINE 3: "Har pal yahan jee bhar jiyo" ---
    # Notes: G4, A4, C5, A4, F4, G4, A4, G4
    {"note": "Har (G4)", "freq": G4, "dur": 0.4},
    {"note": "Pal (A4)", "freq": A4, "dur": 0.4},
    {"note": "Ya (C5)",  "freq": C5, "dur": 0.4},
    {"note": "Han (A4)", "freq": A4, "dur": 0.8}, # Longer pause "Yahaaan"
    
    {"note": "Jee (F4)", "freq": F4, "dur": 0.4},
    {"note": "Bhar (G4)","freq": G4, "dur": 0.4},
    {"note": "Ji (A4)",  "freq": A4, "dur": 0.4},
    {"note": "Yo (G4)",  "freq": G4, "dur": 1.5}, # Final resolve
]

def main():
    print("🎸 Loading Vocal Melody...")
    # Pre-generate audio
    for item in MELODY:
        item["sound"] = generate_string_sound(item["freq"])

    print("🔈 Playing Song...")
    engine = GuitarEngine()
    stream = sd.OutputStream(channels=1, samplerate=SAMPLE_RATE, callback=engine.callback)
    stream.start()
    
    time.sleep(1)

    try:
        # Loop 2 times as requested
        for loop in range(2):
            print(f"\n--- Verse Loop {loop + 1} ---")
            for item in MELODY:
                print(f"🎵 {item['note']}")
                engine.add_sound(item["sound"])
                time.sleep(item["dur"]) 
            
            time.sleep(1.0) # Breath between loops
            
        print("\n✨ Song Complete")
        time.sleep(2)

    except KeyboardInterrupt:
        print("\nStopping...")
    
    stream.stop()
    stream.close()

if __name__ == "__main__":
    main()