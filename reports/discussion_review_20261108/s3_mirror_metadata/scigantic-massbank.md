# MassBank, release 2026.03, open-licence records

MassBank consortium (MassBank Europe / NFDI4Chem). Source: https://github.com/MassBank/MassBank-data/releases/tag/2026.03
(also doi:10.5281/zenodo.3378723). Every MassBank record carries its own licence. Records under a
NonCommercial licence (CC BY-NC, CC BY-NC-SA) are NOT in this mirror; everything else is.

| licence | records in the release | in this mirror |
|---|---|---|
| CC BY 4.0 | 48360 | yes |
| CC BY-NC-SA 4.0 | 33476 | no |
| CC BY-SA 4.0 | 20912 | yes |
| dl-de/by-2-0 | 20658 | yes |
| CC BY-NC 4.0 | 8432 | no |
| CC0 1.0 | 7019 | yes |

MassBank_NISTformat.open.msp holds the upstream MassBank_NISTformat.msp record blocks, unchanged and in
upstream order, for the 96949 kept accessions (149 MSP records with no licence entry in
MassBank.json are left out as well). massbank_open_spectra.parquet holds the same records
as one row per spectrum (metadata columns, the record's licence, peaks as mz / intensity lists).
Built on 2026-10-22 by backend/scripts/build-ms-np-mirrors.py. Attribution: each record's authors and
copyright holder as given at https://massbank.eu/MassBank/RecordDisplay?id=<accession> . Cite MassBank
and the record, not this mirror.

| file | bytes | md5 |
|---|---|---|
| MassBank_NISTformat.open.msp | 97743917 | dafed062a575af54f571cf43177f2782 |
| massbank_open_spectra.parquet | 23611171 | 8fbda467165353851eb112054f19b9e6 |
