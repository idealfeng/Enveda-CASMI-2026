import pickle
from multiprocessing import Pool
from casmi import formula_mass
from fingerprints import fp_packed_v2

class NumpyOnly(pickle.Unpickler):
    def find_class(self, module, name):
        if (module, name) in {('numpy', 'ndarray'), ('numpy', 'dtype'), ('numpy._core.multiarray', '_reconstruct'),
                              ('numpy.core.multiarray', '_reconstruct')}:
            return super().find_class(module, name)
        raise pickle.UnpicklingError(f'blocked {module}.{name}')

with open(COCO / 'coco_meta.pkl', 'rb') as f:
    cm = NumpyOnly(f).load()
coco = pd.DataFrame({'ik14': cm['keys'].astype(str), 'smiles': cm['smiles'].astype(str),
                     'mass': np.load(COCO / 'coco_mass.npy'), 'source': 'coconut'})
tr = pd.read_parquet(DATA / 'train.parquet', columns=['inchikey14', 'normalized_smiles', 'molecular_formula'])
tr = tr.drop_duplicates('inchikey14')
tr = pd.DataFrame({'ik14': tr.inchikey14, 'smiles': tr.normalized_smiles,
                   'mass': tr.molecular_formula.map(formula_mass), 'source': 'train'})
structs = (pd.concat([tr, coco], ignore_index=True).dropna(subset=['mass'])
           .drop_duplicates('ik14').sort_values('mass', ignore_index=True))
with Pool(4) as pool:
    fps = np.stack(pool.map(fp_packed_v2, structs.smiles, chunksize=2000))
structs.to_parquet('/kaggle/working/structures.parquet'); np.save('/kaggle/working/fps.npy', fps)
print(len(structs), fps.shape)
del structs, fps, tr, coco, cm