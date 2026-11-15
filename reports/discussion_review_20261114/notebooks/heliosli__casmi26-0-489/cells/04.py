# House style for our own figures (engine/33_style.py at repo commit 30b76796, without its ink and grid
# colours, so the upstream tiles and tables keep theirs). A later cell imports another `apply`; ours stays as style_apply.
ACCENT = "#d9480f"      # the one colour that means "this is the point"
SECOND = "#1c7ed6"      # used only when two things must be told apart
PALETTE = [ACCENT, SECOND, "#495057", "#adb5bd", "#2b8a3e", "#862e9c"]


def apply() -> None:
    """Set matplotlib defaults. Safe to call more than once."""
    import matplotlib as mpl
    mpl.rcParams.update({
        "figure.figsize": (9, 4.6), "figure.dpi": 110, "savefig.dpi": 160,
        "figure.facecolor": "white", "axes.facecolor": "white",
        "font.size": 11, "axes.titlesize": 13, "axes.titleweight": "semibold", "axes.titlelocation": "left",
        "axes.labelsize": 11, "axes.labelcolor": INK, "text.color": INK,
        "xtick.color": MUTED, "ytick.color": MUTED, "xtick.labelsize": 10, "ytick.labelsize": 10,
        "axes.edgecolor": GRID, "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
        "axes.prop_cycle": mpl.cycler(color=PALETTE),
        "lines.linewidth": 2.0, "legend.frameon": False, "legend.fontsize": 10,
    })


def label_point(ax, x, y, text: str, color: str = ACCENT) -> None:
    """Print the number that matters on the chart, next to the point it describes."""
    ax.annotate(text, (x, y), xytext=(6, 6), textcoords="offset points", color=color,
                fontsize=11, fontweight="semibold")


def first_screen(claim: str, number: str, beats: str | None = None, runtime: str | None = None,
                 accel: str | None = None) -> str:
    """The markdown every busyaprime notebook opens with. Returns it so a builder can write it into cell 0.

    claim   one sentence: what this notebook shows that the reader did not know
    number  the result, with its metric and where it was measured (public LB, CV on stated folds)
    beats   the public work it beats, with that work's number and a link
    runtime wall clock on the stated accelerator
    """
    rows = [f"| result | **{number}** |"]
    if beats:
        rows.append(f"| beats | {beats} |")
    if runtime:
        rows.append(f"| runtime | {runtime}{' on ' + accel if accel else ''} |")
    return f"{claim}\n\n| | |\n|---|---|\n" + "\n".join(rows) + "\n"
style_apply = apply