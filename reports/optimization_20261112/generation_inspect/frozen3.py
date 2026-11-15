from pathlib import Path
import os
import hashlib
import platform
import warnings

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import matplotlib.pyplot as plt
import seaborn as sns
from IPython.display import display, Markdown

from rdkit import Chem, rdBase
from rdkit.Chem import Descriptors, Draw, rdMolDescriptors, rdFingerprintGenerator
from rdkit.Chem.Scaffolds import MurckoScaffold
from rdkit import DataStructs
from sklearn.decomposition import TruncatedSVD
from sklearn.preprocessing import StandardScaler

SEED = 20260915
rng = np.random.default_rng(SEED)
pd.set_option("display.max_colwidth", 100)
pd.set_option("display.max_rows", 100)
sns.set_theme(style="whitegrid", context="notebook")
plt.rcParams.update({"figure.figsize": (11, 5.5), "axes.titleweight": "bold", "figure.dpi": 120})

# Sharp inline figures, with PNG retained for readers that do not support SVG.
from matplotlib_inline.backend_inline import set_matplotlib_formats
set_matplotlib_formats('svg', 'png')
plt.rcParams.update({
    'figure.dpi': 160, 'savefig.dpi': 200, 'savefig.bbox': 'tight',
    'font.size': 12, 'axes.labelsize': 12, 'axes.titlesize': 13,
    'xtick.labelsize': 10, 'ytick.labelsize': 10,
    'axes.spines.top': False, 'axes.spines.right': False,
    'svg.fonttype': 'none', 'figure.facecolor': 'white',
})
