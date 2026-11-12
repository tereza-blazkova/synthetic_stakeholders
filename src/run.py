"""
Run workshops from the command line.

    python -m src.run --family family_1 --run pilot      # 1 pilot workshop
    python -m src.run --family family_1 --run 1-10       # the 10 main runs
    python -m src.run --backend fake --run pilot         # test without a model
    python -m src.run --tier large --protocol full --family family_1 --run 1-10   # UCloud

Long runs: keep the laptop awake and plugged in, e.g.
    caffeinate -i python -m src.run --family family_1 --run 1-10

Logs go to runs/<model>/<run_id>/. An existing run directory is never
overwritten: delete it by hand to redo a run.
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

import yaml

from src.llm import FakeBackend, OllamaBackend
from src.workshop import Workshop
from src.workshop_full import FullWorkshop

ROOT = Path(__file__).resolve().parents[1]


def parse_runs(spec: str, cfg: dict) -> list[tuple[str, int]]:
    """'pilot' -> [('pilot', pilot_seed)]; '1-10' or '3' -> [('run01', seeds[0]), ...]."""
    if spec == "pilot":
        return [("pilot", cfg["study"]["pilot_seed"])]
    lo, _, hi = spec.partition("-")
    seeds = cfg["study"]["seeds"]
    return [(f"run{k:02d}", seeds[k - 1]) for k in range(int(lo), int(hi or lo) + 1)]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--family", help="key under models: in config.yaml (e.g. family_1)")
    p.add_argument("--run", required=True, help="'pilot', a run number, or a range like 1-10")
    p.add_argument("--backend", choices=["ollama", "fake"], default="ollama")
    p.add_argument("--model", help="override the Ollama model tag (smoke tests; logs go to runs/_smoke/)")
    p.add_argument("--protocol", choices=["lite", "full"], default="lite")
    p.add_argument("--tier", choices=["small", "large", "post_review"], default="small",
                   help="small = laptop models (models:), large = UCloud models (models_large:), "
                        "post_review = extra models for B3/B4 (models_post_review:)")
    p.add_argument("--personas", help="persona variant file (post-review B2); needs --condition")
    p.add_argument("--condition", help="post-review condition name: logs go to runs/post_review/<condition>/")
    args = p.parse_args()
    if args.personas and not args.condition:
        sys.exit("--personas needs --condition, so variant runs never land next to the reference runs")
    if args.tier == "post_review" and not args.condition:
        sys.exit("--tier post_review needs --condition")
    if args.condition and (not re.fullmatch(r"[A-Za-z0-9_]+", args.condition) or args.condition == "card"):
        sys.exit("--condition: letters, digits and _ only ('card' is the B1 replay folder)")
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text())

    if args.backend == "fake":
        backend, folder = FakeBackend(), "_fake"
    else:
        models = cfg[{"small": "models", "large": "models_large", "post_review": "models_post_review"}[args.tier]]
        hw = cfg["local"] if args.tier == "small" else cfg["gpu"]
        model = args.model or models[args.family]["model_id"]
        if not model:
            sys.exit(f"no model_id for {args.family} in config.yaml")
        s = cfg["sampling"]
        backend = OllamaBackend(model, num_ctx=hw["num_ctx"], temperature=s["temperature"],
                                max_tokens=s["max_output_tokens"])
        pinned = None if args.model else models[args.family].get("digest")
        if pinned and backend.digest != pinned:
            sys.exit(f"{model}: local digest {backend.digest} != pinned {pinned} in config.yaml")
        unloaded = backend.unload_others() if hw.get("unload_others", True) else []
        if unloaded:
            print(f"unloaded from memory: {', '.join(unloaded)}")
        folder = "_smoke/" + model if args.model else model
    if args.protocol == "full":
        folder = "full/" + folder           # lite runs keep runs/<model>/ as before
    if args.condition:
        folder = f"post_review/{args.condition}/" + folder
    folder = re.sub(r"[^A-Za-z0-9._/-]", "_", folder)
    workshop_cls = FullWorkshop if args.protocol == "full" else Workshop
    kwargs = {"personas_path": Path(args.personas)} if args.personas else {}

    for run_id, seed in parse_runs(args.run, cfg):
        run_dir = ROOT / "runs" / folder / run_id
        if (run_dir / "calls.jsonl").exists():
            if args.condition and not (run_dir / "run_meta.json").exists():
                # post-review only: an interrupted run is moved aside (kept, never scored) and redone
                aside = run_dir.with_name(f"_incomplete_{run_id}_{int(time.time())}")
                run_dir.rename(aside)
                print(f"moved incomplete {run_dir.relative_to(ROOT)} -> {aside.name}; redoing")
            else:
                print(f"skip {run_dir.relative_to(ROOT)}: already exists")
                continue
        print(f"=== {folder} {run_id} (seed {seed}) ===")
        workshop_cls(backend, run_dir, seed, **kwargs).run()


if __name__ == "__main__":
    main()
