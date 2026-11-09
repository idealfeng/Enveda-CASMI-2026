# Enveda-180 H+/H− reference data for CASMI 2026

This Kaggle dataset contains a filtered, derived subset of the public Enveda-180 release: positive `[M+H]+` and negative `[M-H]-` MS/MS reference spectra, plus neutral candidate structures that are present in Enveda-180 but absent from the official competition training catalog.

**Source and attribution:** Christoph A. Krettler, Tobias Kind, Erik DeBloois, Marie Killian, John Prince, James Taylor, Yojana Gadiya, Daniel Domingo-Fernández, August Allen, Viswa Colluru, and David Healey, *Enveda-180: generation of a large open multimodal MS/MS and ion mobility spectral library for drug-like small molecules*, Zenodo record 21346580 (2026), https://doi.org/10.5281/zenodo.21346580.

The source release is licensed **Creative Commons Attribution 4.0 International (CC BY 4.0)**. This derived subset is shared under the same license with attribution. The competition host confirmed that the Enveda-180 Zenodo release is permitted external data: https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/745148.

Files: `enveda180_hplus_hminus_references.parquet` (same-adduct reference peaks, scoring identity, exact neutral mass, and exact-spectrum signature) and `enveda180_only_candidate_aliases.parquet` (3,717 source-only identities and their SMILES/mass aliases). No competition test labels or answers are included.
