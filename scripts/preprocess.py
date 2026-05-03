#!/usr/bin/env python3
"""
Preprocess Umamusume dashboard data into slide JSON for the Preact viewer.

Usage:
    python3 scripts/preprocess.py --repo ../Umamusume_Virgo_Cup_Dashboard --event CM10
    python3 scripts/preprocess.py --event CM11   # uses local data in src/data/
"""

import argparse
import json
import os
import re
import shutil
import pandas as pd
from pathlib import Path

EVENT_CONFIG = {
    # CM6–CM12 QC events using one merged CSV source.
    "CM6": {
        "name": "CM6 QC",
        "icon": "capricorn_icon.png",
        "theme": "default",
        "distance": "Unknown",
        "surface": "Unknown",
        "track": "Unknown",
        "finals_csv": "cm4_cm12_finals.csv",
        "merged_csv": True,
        "cm_id": "CM6",
        "local": True,
    },
    "CM7": {
        "name": "CM7 QC",
        "icon": "capricorn_icon.png",
        "theme": "default",
        "distance": "Unknown",
        "surface": "Unknown",
        "track": "Unknown",
        "finals_csv": "cm4_cm12_finals.csv",
        "merged_csv": True,
        "cm_id": "CM7",
        "local": True,
    },
    "CM8": {
        "name": "CM8 QC",
        "icon": "capricorn_icon.png",
        "theme": "default",
        "distance": "Unknown",
        "surface": "Unknown",
        "track": "Unknown",
        "finals_csv": "cm4_cm12_finals.csv",
        "merged_csv": True,
        "cm_id": "CM8",
        "local": True,
    },
    "CM9": {
        "name": "CM9 QC",
        "icon": "capricorn_icon.png",
        "theme": "default",
        "distance": "Unknown",
        "surface": "Unknown",
        "track": "Unknown",
        "finals_csv": "cm4_cm12_finals.csv",
        "merged_csv": True,
        "cm_id": "CM9",
        "local": True,
    },
    "CM10": {
        "name": "CM10 QC",
        "icon": "aquarius_icon.png",
        "theme": "uma",
        "distance": "Unknown",
        "surface": "Unknown",
        "track": "Unknown",
        "finals_csv": "cm4_cm12_finals.csv",
        "merged_csv": True,
        "cm_id": "CM10",
        "local": True,
    },
    "CM11": {
        "name": "CM11 QC",
        "icon": "pisces_icon.png",
        "theme": "uma",
        "distance": "Unknown",
        "surface": "Unknown",
        "track": "Unknown",
        "finals_csv": "cm4_cm12_finals.csv",
        "merged_csv": True,
        "cm_id": "CM11",
        "local": True,
    },
    "CM12": {
        "name": "CM12 QC",
        "icon": "pisces_icon.png",
        "theme": "uma",
        "distance": "Unknown",
        "surface": "Unknown",
        "track": "Unknown",
        "finals_csv": "cm4_cm12_finals.csv",
        "merged_csv": True,
        "cm_id": "CM12",
        "local": True,
    },
}

COL_IGN = "Unique display name"
COL_OSHI = 'Did you build an "oshi"/niche uma ace this CM?'
COL_QUOTE = 'Optional - Quote in case you win an "Oshi award" this CM to be used in the award'
COL_RESULT = "Finals result?"


def normalize_yes_no(value):
    if pd.isna(value):
        return ""
    raw = str(value).strip().lower()
    return "Yes" if raw in {"yes", "y", "true", "1"} else "No"


def load_dataframes(data_base, cfg):
    # 1) Load the single merged CSV file for the selected event.
    finals_df = pd.read_csv(data_base / cfg["finals_csv"])

    if cfg.get("merged_csv"):
        # 2) Validate required columns from the merged source.
        required = {
            "Meta|CM_ID", "Meta|IGN", "Meta|League", "Finals|Group", "Finals|Result",
            "Finals|ResultsList|Screenshot", "Finals|Winner|Screenshot|Stat1",
            "Meta|Oshi|Built", "podium|trainer_name", "podium|name", "podium|placement", "podium|time",
            "stat|is_user", "stat|ign", "stat|name", "stat|Speed", "stat|Stamina", "stat|Power", "stat|Guts", "stat|Wit"
        }
        missing = [c for c in required if c not in finals_df.columns]
        if missing:
            raise ValueError(f"Merged CSV is missing required columns: {missing}")

        # 3) Slice merged file down to one CM event (CM6, CM7, ... CM12).
        if cfg.get("cm_id"):
            finals_df = finals_df[finals_df["Meta|CM_ID"].astype(str).str.upper() == str(cfg["cm_id"]).upper()].copy()

        # 4) Build stats dataframe used later by slide stat extraction.
        stats_cols = ["stat|is_user", "stat|ign", "stat|name", "stat|Speed", "stat|Stamina", "stat|Power", "stat|Guts", "stat|Wit"]
        stats_missing = [c for c in stats_cols if c not in finals_df.columns]
        if stats_missing:
            raise ValueError(f"Merged CSV is missing stats columns: {stats_missing}")
        stats_df = finals_df[stats_cols].rename(columns={
            "stat|is_user": "is_user",
            "stat|ign": "ign",
            "stat|name": "name",
            "stat|Speed": "Speed",
            "stat|Stamina": "Stamina",
            "stat|Power": "Power",
            "stat|Guts": "Guts",
            "stat|Wit": "Wit",
        }).dropna(subset=["ign", "name"])
        stats_df["is_user"] = stats_df["is_user"].fillna(False).astype(str).str.lower().isin(["true", "1", "yes", "y"])

        # 5) Build podium dataframe used for winner uniqueness checks.
        podium_cols = ["podium|trainer_name", "podium|name", "podium|placement", "podium|time"]
        podium_missing = [c for c in podium_cols if c not in finals_df.columns]
        if podium_missing:
            raise ValueError(f"Merged CSV is missing podium columns: {podium_missing}")
        podium_df = finals_df[podium_cols].rename(columns={
            "podium|trainer_name": "trainer_name",
            "podium|name": "trainee_name",
            "podium|placement": "placement",
            "podium|time": "time",
        }).dropna(subset=["trainer_name", "trainee_name", "placement"])
        podium_df["placement"] = pd.to_numeric(podium_df["placement"], errors="coerce")
        podium_df = podium_df.dropna(subset=["placement"])
        podium_df["placement"] = podium_df["placement"].astype(int)

        return finals_df, podium_df, stats_df
    raise ValueError("This workflow now supports merged_csv events only.")

DEFAULT_COSTUME = {
    "Rice Shower": "[Rosy Dreams] Rice Shower",
}

ALT_ART = {
    "[Vampire Makeover!] Rice Shower": "Rice_Shower_(Alt).png",
}


def main():
    parser = argparse.ArgumentParser(description="Generate oshi award slide data")
    parser.add_argument("--repo", help="Path to Umamusume_Virgo_Cup_Dashboard repo (optional for local events)")
    parser.add_argument("--event", required=True, choices=EVENT_CONFIG.keys(), help="Event ID")
    args = parser.parse_args()

    cfg = EVENT_CONFIG[args.event]
    project_root = Path(__file__).resolve().parent.parent

    if cfg.get("local"):
        data_base = project_root / "src" / "data"
        umas_dir = None
    else:
        if not args.repo:
            parser.error(f"--repo is required for {args.event}")
        data_base = Path(args.repo).resolve()
        umas_dir = data_base / "assets" / "umas"

    finals_df, podium_df, stats_df = load_dataframes(data_base, cfg)

    print(f"Loaded {len(finals_df)} CSV rows, {len(podium_df)} podium rows, {len(stats_df)} stat rows")

    selected_rows = finals_df[
        (finals_df["Meta|League"] == "Graded (No Uma Restrictions)")
        & (finals_df["Finals|Group"] == "A Finals")
        & (finals_df["Finals|Result"] == "1st")
        & finals_df["Finals|ResultsList|Screenshot"].notna()
        & finals_df["Finals|Winner|Screenshot|Stat1"].notna()
        & (finals_df["Finals|ResultsList|Screenshot"].astype(str).str.strip() != "")
        & (finals_df["Finals|Winner|Screenshot|Stat1"].astype(str).str.strip() != "")
    ]
    print(f"Screenshot-qualified 1st-place winners in CSV: {len(selected_rows)}")

    race_winners = podium_df[podium_df["placement"] == 1]
    uma_win_counts = race_winners["trainee_name"].value_counts()
    unique_umas = set(uma_win_counts[uma_win_counts == 1].index)
    print(f"Unique winning umas (appeared exactly once): {len(unique_umas)}")

    slides = []
    images_needed = set()
    claimed_umas = set()

    for _, row in selected_rows.iterrows():
        ign = row["Meta|IGN"]
        quote = row["Meta|Oshi|Quote"] if ("Meta|Oshi|Quote" in row and pd.notna(row["Meta|Oshi|Quote"])) else ""
        if normalize_yes_no(row["Meta|Oshi|Built"]) != "Yes":
            print(f"  SKIP {ign}: Meta|Oshi|Built is not Yes")
            continue

        player_wins = race_winners[race_winners["trainer_name"] == ign]
        if player_wins.empty:
            stat_match = stats_df[(stats_df["ign"] == ign) & (stats_df["is_user"] == True)]
            if stat_match.empty:
                stat_match = stats_df[stats_df["ign"] == ign]
            if not stat_match.empty:
                candidate = stat_match.iloc[0]["name"]
                candidate_wins = race_winners[race_winners["trainee_name"] == candidate]
                for _, cw in candidate_wins.iterrows():
                    pod_trainer = cw["trainer_name"].lower()
                    ign_lower = ign.lower()
                    if (pod_trainer.startswith(ign_lower[:3])
                            or ign_lower.startswith(pod_trainer[:3])
                            or pod_trainer in ign_lower
                            or ign_lower in pod_trainer):
                        player_wins = candidate_wins[candidate_wins.index == cw.name]
                        print(f"  Resolved {ign} via stats fallback -> {candidate} (trainer={cw['trainer_name']})")
                        break
            if player_wins.empty:
                print(f"  SKIP {ign}: no podium win found")
                continue

        win = player_wins.iloc[0]
        trainee = win["trainee_name"]
        time_val = win["time"] if pd.notna(win["time"]) else ""

        if trainee not in unique_umas:
            print(f"  SKIP {ign}: {trainee} not unique ({uma_win_counts.get(trainee, 0)} wins)")
            continue

        if trainee in claimed_umas:
            print(f"  SKIP {ign}: {trainee} already claimed by another player")
            continue
        claimed_umas.add(trainee)

        has_user_flag = stats_df["is_user"].any()
        if has_user_flag:
            stat_row = stats_df[
                (stats_df["ign"] == ign)
                & (stats_df["name"] == trainee)
                & (stats_df["is_user"] == True)
            ]
            if stat_row.empty:
                stat_row = stats_df[
                    (stats_df["ign"] == ign) & (stats_df["is_user"] == True)
                ]
        else:
            stat_row = stats_df[
                (stats_df["ign"] == ign) & (stats_df["name"] == trainee)
            ]
            if stat_row.empty:
                stat_row = stats_df[stats_df["ign"] == ign]

        if not stat_row.empty:
            s = stat_row.iloc[0]
            stats = {
                "speed": int(s["Speed"]),
                "stamina": int(s["Stamina"]),
                "power": int(s["Power"]),
                "guts": int(s["Guts"]),
                "wit": int(s["Wit"]),
            }
        else:
            print(f"  WARN {ign}: no stats found, using zeroes")
            stats = {"speed": 0, "stamina": 0, "power": 0, "guts": 0, "wit": 0}

        images_needed.add(trainee)

        slides.append({
            "ign": ign,
            "trainee_name": trainee,
            "uma_image": f"umas/{trainee}.png",
            "time": time_val,
            "result": "1st",
            "quote": quote,
            "stats": stats,
        })

    for slide_entry in slides:
        trainee = slide_entry["trainee_name"]

        if trainee in ALT_ART:
            alt_path = project_root / "public" / "umas" / ALT_ART[trainee]
            if alt_path.exists():
                slide_entry["full_art_image"] = f"umas/{ALT_ART[trainee]}"
                print(f"  Full art assigned (alt): {trainee} -> {ALT_ART[trainee]}")
                continue

        base_name = re.sub(r"\[.*?\]\s*", "", trainee).strip()
        full_art_name = base_name.replace(" ", "_") + "_(Race).png"
        full_art_path = project_root / "public" / "umas" / full_art_name
        if full_art_path.exists():
            if base_name in DEFAULT_COSTUME and DEFAULT_COSTUME[base_name] != trainee:
                continue
            slide_entry["full_art_image"] = f"umas/{full_art_name}"
            print(f"  Full art assigned: {trainee} -> {full_art_name}")

    print(f"\nGenerated {len(slides)} slides")

    data_dir = project_root / "src" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    event_data = {
        "event": {
            "name": cfg["name"],
            "id": args.event,
            "icon": cfg["icon"],
            "theme": cfg.get("theme", "default"),
            "distance": cfg["distance"],
            "surface": cfg["surface"],
            "track": cfg["track"],
        },
        "slides": slides,
    }

    json_path = data_dir / f"slides-{args.event.lower()}.json"
    with open(json_path, "w") as f:
        json.dump(event_data, f, indent=2, ensure_ascii=False)
    print(f"Wrote {json_path}")

    index_path = data_dir / "index.json"
    if index_path.exists():
        with open(index_path) as f:
            index = json.load(f)
    else:
        index = {"events": []}

    existing = {e["id"] for e in index["events"]}
    entry = {
        "id": args.event,
        "name": cfg["name"],
        "icon": cfg["icon"],
        "file": f"slides-{args.event.lower()}.json",
        "slideCount": len(slides),
    }
    if args.event in existing:
        index["events"] = [entry if e["id"] == args.event else e for e in index["events"]]
    else:
        index["events"].append(entry)

    index["events"].sort(key=lambda e: int(e["id"].replace("CM", "")))
    with open(index_path, "w") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)
    print(f"Updated {index_path}")

    # --- Write winners JSON and Markdown ---
    out_dir = project_root / "output"
    out_dir.mkdir(parents=True, exist_ok=True)

    base_name_fn = lambda t: re.sub(r"\[.*?\]\s*", "", t).strip()

    winners = []
    for s in slides:
        winners.append({
            "ign": s["ign"],
            "trainee_name": s["trainee_name"],
            "base_name": base_name_fn(s["trainee_name"]),
            "time": s["time"],
            "stats": s["stats"],
            "quote": s["quote"],
        })

    winners_json_path = out_dir / f"winners-{args.event.lower()}.json"
    with open(winners_json_path, "w") as f:
        json.dump({
            "event": args.event,
            "name": cfg["name"],
            "track": cfg["track"],
            "winners": winners,
        }, f, indent=2, ensure_ascii=False)
    print(f"Wrote {winners_json_path}")

    winners_md_path = out_dir / f"winners-{args.event.lower()}.md"
    with open(winners_md_path, "w") as f:
        f.write(f"# {cfg['name']} ({args.event}) — Oshi's Champion Awardees\n\n")
        f.write(f"**Track:** {cfg['track']}  \n")
        f.write(f"**Winners:** {len(winners)}\n\n")
        f.write("---\n\n")
        for i, w in enumerate(winners, 1):
            total = sum(w["stats"].values())
            f.write(f"### {i}. {w['ign']}\n\n")
            f.write(f"**Uma:** {w['trainee_name']}  \n")
            f.write(f"**Time:** {w['time']}  \n")
            f.write(f"**Stats:** {w['stats']['speed']} / {w['stats']['stamina']} / {w['stats']['power']} / {w['stats']['guts']} / {w['stats']['wit']} (Total: {total})  \n")
            if w["quote"]:
                f.write(f"\n> {w['quote']}\n")
            f.write("\n")
    print(f"Wrote {winners_md_path}")

    umas_out = project_root / "public" / "umas"
    umas_out.mkdir(parents=True, exist_ok=True)
    if umas_dir:
        copied = 0
        for name in images_needed:
            src = umas_dir / f"{name}.png"
            dst = umas_out / f"{name}.png"
            if src.exists():
                shutil.copy2(src, dst)
                copied += 1
            else:
                print(f"  WARN image not found: {src.name}")
        print(f"Copied {copied}/{len(images_needed)} images to {umas_out}")
    else:
        missing = [n for n in images_needed if not (umas_out / f"{n}.png").exists()]
        if missing:
            print(f"  WARN {len(missing)} images not in public/umas/: {', '.join(missing)}")
        print(f"Skipped image copy (local mode, no --repo source)")


if __name__ == "__main__":
    main()
