# ── Session: paths, run mode, design tokens and small display helpers ─────────────────────────
import os, sys, re, io, json, time, math, base64, shutil, hashlib, subprocess, collections, warnings
from pathlib import Path

NB_T0 = time.time()
warnings.filterwarnings('ignore')
ROOT = Path('/kaggle/working'); ROOT.mkdir(parents=True, exist_ok=True); os.chdir(ROOT)
INPUT = Path('/kaggle/input')
CODE = ROOT / 'p2s_code'; CODE.mkdir(exist_ok=True)

import numpy as np
import pandas as pd
from IPython.display import display, HTML, FileLink

# Design tokens: chart ink and a fixed categorical order (identity never follows rank).
INK, INK2, MUTED = '#0b0b0b', '#52514e', '#898781'
GRID, AXIS, SURFACE, CARD = '#e1e0d9', '#c3c2b7', '#fcfcfb', '#f7f8fb'
BLUE, ORANGE, AQUA, YELLOW, MAGENTA, GREEN, VIOLET, RED = (
    '#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#6250d6', '#e34948')
QUIET_GRAY = '#c9c8c1'
ROLE = {'main': BLUE, 'engine2': ORANGE, 'pubchem': AQUA, 'new': VIOLET}
FONT = "system-ui,-apple-system,'Segoe UI',Roboto,sans-serif"

import matplotlib
import matplotlib.pyplot as plt
plt.rcParams.update({
    'figure.facecolor': SURFACE, 'axes.facecolor': SURFACE, 'savefig.facecolor': SURFACE,
    'font.size': 10.5, 'axes.titlesize': 12.5, 'axes.titleweight': 'bold', 'axes.titlelocation': 'left',
    'axes.titlecolor': INK, 'axes.titlepad': 10, 'axes.labelcolor': INK2, 'axes.edgecolor': AXIS,
    'axes.linewidth': 0.8, 'xtick.color': AXIS, 'ytick.color': AXIS, 'xtick.labelcolor': INK2,
    'ytick.labelcolor': INK2, 'axes.grid': True, 'grid.color': GRID, 'grid.linewidth': 0.8,
    'grid.linestyle': '-', 'axes.axisbelow': True, 'axes.spines.top': False, 'axes.spines.right': False,
    'legend.frameon': False, 'legend.fontsize': 10, 'figure.dpi': 110, 'savefig.dpi': 160,
    'savefig.bbox': 'tight'})
try:
    from matplotlib_inline.backend_inline import set_matplotlib_formats
    set_matplotlib_formats('retina')
except Exception:
    pass


def tiles(items):
    """A row of stat tiles: items = [(label, value, note), ...]."""
    cells = ''.join(
        f'<div style="display:inline-block;vertical-align:top;min-width:150px;margin:0 10px 10px 0;'
        f'padding:12px 16px;border-radius:12px;background:#ffffff;border:1px solid rgba(11,11,11,0.10);">'
        f'<div style="font-size:12px;color:{INK2};">{label}</div>'
        f'<div style="font-size:25px;font-weight:650;color:{INK};line-height:1.3;">{value}</div>'
        f'<div style="font-size:11.5px;color:{MUTED};">{note}</div></div>' for label, value, note in items)
    display(HTML(f'<div style="font-family:{FONT};margin:4px 0 2px;">{cells}</div>'))


def note(title, text, color=VIOLET):
    display(HTML(f'<div style="font-family:{FONT};border-left:4px solid {color};background:{CARD};'
                 f'padding:10px 14px;border-radius:8px;margin:8px 0;font-size:13.5px;line-height:1.5;">'
                 f'<b style="color:{INK};">{title}</b> <span style="color:{INK2};">{text}</span></div>'))


def table_html(frame, highlight=None, numeric=()):
    """Plain, readable HTML table; numbers right-aligned; `highlight` = index label of a row to emphasise."""
    align = {c: 'right' if c in set(numeric) else 'left' for c in frame.columns}
    head = ''.join(f'<th style="text-align:{align[c]};padding:7px 12px;border-bottom:1px solid {AXIS};'
                   f'color:{INK2};font-weight:600;background:transparent;">{c}</th>' for c in frame.columns)
    body = []
    for idx, row in frame.iterrows():
        on = highlight is not None and idx == highlight
        style = 'background:#efedfb;font-weight:600;' if on else 'background:transparent;'
        body.append(f'<tr style="{style}">' + ''.join(
            f'<td style="text-align:{align[c]};padding:7px 12px;border-bottom:1px solid {GRID};color:{INK};'
            f'font-variant-numeric:tabular-nums;">{v}</td>' for c, v in zip(frame.columns, row.values)) + '</tr>')
    display(HTML(f'<table style="font-family:{FONT};font-size:13px;border-collapse:collapse;margin:6px 0 10px;">'
                 f'<thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table>'))


def minutes(seconds):
    return f'{seconds / 60:,.1f} min' if seconds >= 60 else f'{seconds:,.0f} s'


def gpu_name():
    try:
        out = subprocess.run(['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'],
                             capture_output=True, text=True, timeout=30).stdout.strip()
        return ' + '.join(x.strip() for x in out.splitlines() if x.strip()) or 'none'
    except Exception:
        return 'none'


# Run mode: the commit run sees the visible format example; the scoring rerun sees the hidden test.
COMP = next((p for p in (INPUT / 'competitions/enveda-CASMI26-molecule-id-mass-spectra',
                         INPUT / 'enveda-CASMI26-molecule-id-mass-spectra',
                         INPUT / 'enveda-casmi26-molecule-id-mass-spectra')
             if all((p / f).is_file() for f in ('train.parquet', 'test.parquet', 'sample_submission.csv'))), None)
assert COMP is not None, 'Attach the competition data (enveda-CASMI26-molecule-id-mass-spectra)'
_ids = pd.read_parquet(COMP / 'test.parquet', columns=['spectrum_id']).spectrum_id.astype(str)
TEST_SIGNATURE = hashlib.md5(','.join(sorted(_ids)).encode()).hexdigest()
del _ids
IS_RERUN = bool(os.getenv('KAGGLE_IS_COMPETITION_RERUN')) or TEST_SIGNATURE != '654e030e4173780e945252b4a5adf70b'
RUN_PIPELINE = IS_RERUN or COMMIT_MODE != 'fast'
SHOW = not IS_RERUN                      # figures are drawn for readers; the scoring rerun skips them
SAMPLE_IDS = pd.read_csv(COMP / 'sample_submission.csv', dtype=str).molecule_id.tolist()
assert VARIANT in ('V0', 'V1', 'V2', 'V3', 'V4', 'CUSTOM'), VARIANT

GPU = gpu_name()
MODE = 'Scoring rerun' if IS_RERUN else ('Commit · smoke run' if RUN_PIPELINE else 'Commit · fast path')
tiles([('Run mode', MODE, 'hidden test' if IS_RERUN else 'visible format example'),
       ('Variant', VARIANT, 'set in the configuration cell'),
       ('Accelerator', GPU.split(' + ')[0] if GPU != 'none' else 'none', GPU if ' + ' in GPU else 'GPU required'),
       ('Python', '.'.join(map(str, sys.version_info[:3])), 'pipeline expects 3.12'),
       ('Answer rows', f'{len(SAMPLE_IDS):,}', 'molecules in sample_submission')])