#!/usr/bin/env python3
"""Synthesizes Canarito/Sounds/canarito-alert.caf: our own sound, no sampled or licensed audio.

A two-tone chime, G5 then C6 (a rising fourth, like a public announcement chime: calm, not alarming),
five times, every 2.4 s, about 12 s. The owner picked it from five candidates. No siren sweep, no buzzer, no hard edges: people who lived an
earthquake should not hear a trauma sound, but it has to be loud and different from every iOS default.
iOS plays a custom push sound for at most 30 s.
"""
import math, struct, subprocess, sys, wave
from pathlib import Path

RATE = 44100
NOTES = [783.99, 1046.5]             # G5 C6
STEP = 0.6                            # seconds between the two tones
REPEATS, REPEAT_EVERY, TOTAL = 5, 2.4, 12.0
# Chime: a slow-dying fundamental with soft harmonics, warmer than a struck bell.
PARTIALS = [(1.0, 1.0, 0.9), (2.0, 0.2, 1.8), (3.0, 0.08, 3.0)]  # ratio, level, decay rate

def bell(buffer, start, freq):
    first = int(start * RATE)
    for n in range(first, min(len(buffer), first + int(2.2 * RATE))):
        t = (n - first) / RATE
        attack = min(1.0, t / 0.008)                      # 8 ms ramp: no click
        value = sum(level * math.exp(-decay * t) * math.sin(2 * math.pi * freq * ratio * t)
                    for ratio, level, decay in PARTIALS)
        buffer[n] += attack * value

def main(out: Path):
    buffer = [0.0] * int(TOTAL * RATE)
    for repeat in range(REPEATS):
        for index, freq in enumerate(NOTES):
            bell(buffer, repeat * REPEAT_EVERY + index * STEP, freq)
    peak = max(abs(x) for x in buffer)
    gain = 0.89 / peak                                    # about -1 dBFS: as loud as the format allows
    fade = int(0.25 * RATE)
    for i in range(fade):                                 # the last tail ends at zero
        buffer[-1 - i] *= i / fade
    wav = out.with_suffix(".wav")
    with wave.open(str(wav), "wb") as file:
        file.setnchannels(1); file.setsampwidth(2); file.setframerate(RATE)
        file.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, x * gain)) * 32767)) for x in buffer))
    subprocess.run(["afconvert", "-f", "caff", "-d", "LEI16", str(wav), str(out)], check=True)
    wav.unlink()
    print(f"{out} {out.stat().st_size // 1024} KB")

if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "Canarito/Sounds/canarito-alert.caf"))
