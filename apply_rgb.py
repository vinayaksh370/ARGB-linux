import json
import subprocess
import sys


def run_facer(script, args):
    cmd = ["python3", script] + [str(a) for a in args]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"FAILED: {' '.join(cmd)}\n{result.stderr}", file=sys.stderr)
        return False
    return True


def main():
    if len(sys.argv) != 2:
        print("Usage: apply_rgb.py '<json config>'", file=sys.stderr)
        sys.exit(1)

    cfg = json.loads(sys.argv[1])
    script = cfg["facer_script"]
    mode = cfg["mode"]
    brightness = cfg.get("brightness", 100)
    speed = cfg.get("speed", 0)
    direction = cfg.get("direction", 1)

    ok = True

    if mode == 0:
        # Static mode: one call per zone
        for z in cfg.get("zones", []):
            args = [
                "-m", 0, "-z", z["zone"],
                "-cR", z["r"], "-cG", z["g"], "-cB", z["b"],
                "-b", brightness,
            ]
            ok = run_facer(script, args) and ok
    else:
        # Animated modes: single global call
        color = cfg.get("color", {"r": 255, "g": 255, "b": 255})
        args = ["-m", mode, "-s", speed, "-b", brightness]
        if mode in (1, 4, 5):  # breath, shifting, zoom accept a color
            args += ["-cR", color["r"], "-cG", color["g"], "-cB", color["b"]]
        if mode == 3:  # wave accepts direction
            args += ["-d", direction]
        ok = run_facer(script, args) and ok

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()