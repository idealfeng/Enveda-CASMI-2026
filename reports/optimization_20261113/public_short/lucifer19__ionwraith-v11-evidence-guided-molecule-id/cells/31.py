# Figure cell: the score ladder and a short pipeline animation. Drawn from public numbers and this notebook's own settings.
# It never reads or writes submission.csv and any problem here is only printed.
try:
    if SHOW:
        import matplotlib.pyplot as plt
        from PIL import Image, ImageDraw, ImageFont

        LADDER = [("SHARDWRIGHT v8", 0.161), ("IonWraith v11", 0.274), ("IonWraith v13", 0.274),
                  ("IonWraith v16 (V8 = 'BOTH')", 0.461), ("Gold Apex V22, V8 = 'MASS' (public)", 0.481),
                  ("+ library rank-1 rule (public, this code)", 0.487)]
        fig, ax = plt.subplots(figsize=(9.5, 3.6))
        fig.subplots_adjust(left=0.36, right=0.97, bottom=0.18, top=0.88)
        names = [a for a, _ in LADDER]
        vals = [b for _, b in LADDER]
        cols = [QUIET_GRAY] * 1 + [BLUE] * 3 + [VIOLET] * 2
        bars = ax.barh(names[::-1], vals[::-1], color=cols[::-1])
        for b, v in zip(bars, vals[::-1]):
            ax.text(v + 0.006, b.get_y() + b.get_height() / 2, f"{v:.3f}", va="center", color=INK2, fontsize=10)
        ax.set_xlim(0, 0.56)
        ax.set_xlabel("MRR@25 on the public board (blue: my runs, violet: authors' public scores)")
        ax.set_title("From my own engine to the shared frontier")
        ax.grid(axis="y", visible=False)
        fig.savefig(ROOT / "ionwraith_v17_ladder.png")
        plt.show()

        W, H = 1160, 420
        STAGES_ = [("candidates", "library + natural-product pools"), ("neural", "two spectrum models, 50/50 z-score"),
                   ("consensus", f"ranks 2-25 at w_mid {CUSTOM['w_mid']:.2f}"), ("fragments", "physical check moves the leader"),
                   ("priors", f"NP {NP_W:.2f} | lib {SPEC_W:.2f} | PubChem {POP_W:.2f}"), ("mass", f"timsTOF prior, {MASS_FREE:.0f} ppm free zone"),
                   ("library hit", "measured reference match goes to rank 1")]
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", 15)
            big = ImageFont.truetype("DejaVuSans-Bold.ttf", 26)
        except Exception:
            font = big = ImageFont.load_default()
        frames = []
        n = len(STAGES_)
        for f in range(70):
            t = f / 69 * (n - 0.001)
            cur = int(t)
            im = Image.new("RGB", (W, H), "#0b1020")
            d = ImageDraw.Draw(im)
            d.text((30, 18), "IonWraith v17 - the layers, in order", fill="#e8e6ff", font=big)
            for i, (a, b) in enumerate(STAGES_):
                x = 30 + i * 160
                on = i <= cur
                d.rounded_rectangle([x, 110, x + 148, 260], 16, fill="#2a78d6" if on else "#1c2440", outline="#6250d6" if i == cur else "#2f3a63", width=3)
                d.text((x + 10, 122), a, fill="white", font=font)
                words, line, lines = b.split(), "", []
                for w in words:
                    if len(line) + len(w) + 1 > 15:
                        lines.append(line)
                        line = w
                    else:
                        line = (line + " " + w).strip()
                lines.append(line)
                for k, ln in enumerate(lines[:5]):
                    d.text((x + 10, 150 + 20 * k), ln, fill="#cfd6ff", font=font)
                if i < n - 1:
                    d.line([x + 148, 185, x + 160, 185], fill="#6250d6" if i < cur else "#2f3a63", width=4)
            px = 30 + min(t, n - 1) * 160 + 74
            d.ellipse([px - 9, 292, px + 9, 310], fill="#eda100")
            d.text((30, 340), "the pipeline restores the previous layer on any error, a late start or a failed check", fill="#898fb5", font=font)
            d.text((30, 372), "rank 1 is where this lineage gains and loses; the last layer only acts on a measured match", fill="#898fb5", font=font)
            frames.append(im)
        frames[0].save(ROOT / "ionwraith_v17_layers.gif", save_all=True, append_images=frames[1:], duration=90, loop=0, optimize=True)
        try:
            from IPython.display import Image as IPImage
            display(IPImage(filename=str(ROOT / "ionwraith_v17_layers.gif")))
        except Exception as shown_exc:  # noqa: BLE001
            print("animation written, not shown:", repr(shown_exc))
        print("Layer animation:", len(frames), "frames written to ionwraith_v17_layers.gif")
except Exception as exc:  # noqa: BLE001 - a figure must never touch the answer
    print("figure cell skipped:", repr(exc))
