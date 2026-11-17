"""Read only allowed query metadata; do not read truth, structures, peaks or scores."""
from pathlib import Path
from collections import Counter
import hashlib
import json
import math
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / 'runs/validation_pilot_v2_20261104/queries.parquet'
OUT = ROOT / 'reports/new_paradigm_20261115/old48_native_condition_audit.json'
ALLOWED = ['molecule_id', 'spectrum_id', 'instrument_type', 'instrument',
           'adduct', 'collision_energy_ev', 'collision_energy']
MODES = {'[M+H]+', '[M-H]-', '[M]+', '[M]-'}

def finite_energies(value):
    if value is None:
        return []
    values = value if isinstance(value, (tuple, list)) else [value]
    out = []
    for item in values:
        try:
            number = float(item)
            if math.isfinite(number):
                out.append(number)
        except (TypeError, ValueError):
            pass
    return out

schema = pq.ParquetFile(INPUT).schema_arrow.names
columns = [key for key in ALLOWED if key in schema]
rows = pq.read_table(INPUT, columns=columns).to_pylist()
instrument_field = next((x for x in ['instrument_type', 'instrument'] if x in columns), None)
energy_field = next((x for x in ['collision_energy_ev', 'collision_energy'] if x in columns), None)
instruments, adducts = Counter(), Counter()
eligible, known_ce, hcd_rows = [], 0, 0
for row in rows:
    instrument = row.get(instrument_field) if instrument_field else None
    instrument = '<missing>' if instrument is None else str(instrument)
    instruments[instrument] += 1
    adduct = row.get('adduct')
    adducts[str(adduct)] += 1
    energies = finite_energies(row.get(energy_field)) if energy_field else []
    known_ce += bool(energies)
    is_hcd = instrument.strip().upper() == 'HCD'
    hcd_rows += is_hcd
    if is_hcd and adduct in MODES and energies:
        eligible.append({**row, 'finite_collision_energies_ev': energies})
eligible.sort(key=lambda x: (str(x.get('molecule_id')), str(x.get('spectrum_id'))))
selected, seen = [], set()
for row in eligible:
    mid = row['molecule_id']
    if mid not in seen:
        selected.append(row)
        seen.add(mid)
    if len(selected) == 2:
        break
report = {'source': str(INPUT), 'source_sha256': hashlib.sha256(INPUT.read_bytes()).hexdigest(),
          'rows': len(rows), 'query_ids': len({row.get('molecule_id') for row in rows}),
          'read_columns': columns, 'truth_or_structures_or_peaks_read': False,
          'instrument_field': instrument_field, 'energy_field': energy_field,
          'instrument_counts': dict(instruments), 'adduct_counts': dict(adducts),
          'known_ce_rows': known_ce, 'hcd_rows': hcd_rows,
          'eligible_hcd_supported_adduct_known_ce_rows': len(eligible),
          'eligible_query_ids': len({x['molecule_id'] for x in eligible}),
          'deterministic_selection': selected,
          'selection_rule': 'sort molecule_id then spectrum_id, first max2 unique IDs; raw HCD only; no instrument remapping',
          'interpretation': ('No native-condition query selected; missing instrument metadata must not be relabeled HCD'
                             if not selected else 'Native metadata eligibility only; no candidate scoring performed')}
OUT.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, indent=2))
