#!/usr/bin/env python3
"""Create a visual QA contact sheet from Bitcoin chart outputs."""

import argparse
import math
import sys
import textwrap
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

from run_all_reports import REPORTS, filter_reports, script_dir


def parse_args():
    parser = argparse.ArgumentParser(description="Create a Bitcoin chart contact sheet for visual QA.")
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        metavar="TEXT",
        help="Include only reports whose name, script path, or output filename contains TEXT. Can be repeated.",
    )
    parser.add_argument("--cols", type=int, default=4, help="Number of columns in the contact sheet.")
    parser.add_argument(
        "--output",
        type=Path,
        default=script_dir / "visual_qa_contact_sheet.png",
        help="Output PNG path. The default repo-local preview is ignored by git.",
    )
    parser.add_argument("--thumb-width", type=int, default=900, help="Thumbnail width in pixels.")
    parser.add_argument("--thumb-height", type=int, default=560, help="Thumbnail height in pixels.")
    return parser.parse_args()


def load_thumbnail(path, size):
    """Load a PNG as a centered RGB thumbnail array."""
    with Image.open(path) as image:
        image = image.convert("RGB")
        image.thumbnail(size, Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", size, "black")
        offset = ((size[0] - image.width) // 2, (size[1] - image.height) // 2)
        canvas.paste(image, offset)
        return np.asarray(canvas)


def collect_chart_outputs(filters):
    reports = filter_reports(REPORTS, filters)
    outputs = []
    missing = []
    for report in reports:
        output_path = report["path"].parent / report["output"]
        if output_path.exists():
            outputs.append((report["name"], output_path))
        else:
            missing.append((report["name"], output_path))
    return outputs, missing


def main():
    args = parse_args()
    outputs, missing = collect_chart_outputs(args.only)
    if not outputs:
        print("ERROR: No chart outputs found for the requested filters.", file=sys.stderr)
        if missing:
            for name, path in missing:
                print(f"  Missing: {name} ({path})", file=sys.stderr)
        sys.exit(1)

    cols = max(1, args.cols)
    rows = math.ceil(len(outputs) / cols)
    fig_width = cols * 4.6
    fig_height = rows * 3.35
    fig, axes = plt.subplots(rows, cols, figsize=(fig_width, fig_height), facecolor="black")
    axes = np.atleast_1d(axes).ravel()

    for ax, (name, path) in zip(axes, outputs):
        ax.imshow(load_thumbnail(path, (args.thumb_width, args.thumb_height)))
        ax.set_title(textwrap.fill(name, 26), color="white", fontsize=10, fontweight="bold", pad=8)
        ax.axis("off")

    for ax in axes[len(outputs):]:
        ax.axis("off")

    fig.suptitle("Bitcoin Chart Visual QA Contact Sheet", color="white", fontsize=18, fontweight="bold", y=0.997)
    fig.tight_layout(pad=1.4)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=160, facecolor="black", bbox_inches="tight")
    plt.close(fig)

    print(f"Contact sheet saved as '{args.output}' with {len(outputs)} charts")
    if missing:
        print(f"Skipped {len(missing)} missing chart outputs")


if __name__ == "__main__":
    main()
