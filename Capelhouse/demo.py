"""Generate small synthetic audio samples for the isolated demo and smoke tests."""
import argparse
import json
import math
from pathlib import Path
import struct
import wave


def create_demo(folder):
    folder = Path(folder).resolve()
    incoming = folder / "Entrada"
    incoming.mkdir(parents=True, exist_ok=True)
    for index, name in enumerate(("01 - Brisa", "02 - Horizonte", "03 - Noche")):
        path = incoming / f"{name} (audio de prueba).wav"
        if path.exists():
            continue
        sample_rate = 22050
        frames = bytearray()
        for sample in range(sample_rate * 16):
            time = sample / sample_rate
            beat = (time * (2 + index * .15)) % 1
            kick = math.sin(2 * math.pi * 65 * time) * math.exp(-beat * 22)
            chord = sum(math.sin(2 * math.pi * f * time) for f in (220, 275, 330)) / 3
            fade = min(1, time * 5, (16 - time) * 5)
            value = int(5000 * fade * (.6 * kick + .4 * chord))
            frames.extend(struct.pack("<h", value))
        with wave.open(str(path), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(sample_rate)
            output.writeframes(frames)
    config = folder / "demo.json"
    if not config.exists():
        config.write_text(json.dumps({"entrada": str(incoming), "biblioteca": str(folder / "Biblioteca"),
                                      "generos": ["House", "Techno", "Melodic House"], "tracks": []}, indent=2), encoding="utf-8")
    return config


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=Path)
    print(create_demo(parser.parse_args().folder))
