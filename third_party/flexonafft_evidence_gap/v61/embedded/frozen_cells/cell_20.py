# EDA has finished: release scalar tables and RDKit objects before constructing the search index.
import gc
for _name in ("train", "unique_structures", "descriptor_sample", "desc", "fp_sample", "records",
              "preview_pool", "representatives", "mols", "X", "projection", "library_pairs"):
    globals().pop(_name, None)
plt.close("all")
gc.collect()
