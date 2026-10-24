"""Run the full Python pipeline (download -> indices -> trends -> figures)."""
import runpy
from pathlib import Path

STEPS = ["01_download_stations", "02_download_daily", "03_download_ahccd",
         "04_compute_indices", "05_compute_trends", "06_make_figures"]

if __name__ == "__main__":
    for step in STEPS:
        print(f"\n=== {step} ===")
        runpy.run_path(str(Path(__file__).parent / "scripts" / f"{step}.py"), run_name="__main__")
