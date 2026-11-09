"""Record the actual local runtime without reading account credentials."""
import importlib.metadata
import json
from pathlib import Path
import platform
import shutil
import sys

import psutil
import torch

root = Path(__file__).resolve().parents[1]
packages = {}
for name in ['numpy', 'pandas', 'pyarrow', 'scipy', 'scikit-learn', 'numba', 'rdkit', 'torch', 'lightgbm']:
    try:
        packages[name] = importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        packages[name] = None
report = {
    'platform': platform.platform(),
    'python': platform.python_version(),
    'executable': sys.executable,
    'packages': packages,
    'cuda_runtime': torch.version.cuda,
    'cuda_available': torch.cuda.is_available(),
    'memory_total_bytes': psutil.virtual_memory().total,
    'memory_available_bytes': psutil.virtual_memory().available,
    'disk_free_bytes': shutil.disk_usage(root).free,
}
if torch.cuda.is_available():
    report['gpu'] = torch.cuda.get_device_name(0)
    report['gpu_memory_bytes'] = torch.cuda.get_device_properties(0).total_memory
    # Verify a real CUDA kernel, not just driver discovery.
    x = torch.arange(16, dtype=torch.float32, device='cuda')
    report['cuda_kernel_check'] = float((x*x).sum().item()) == 1240.0
output = root/'reports/reproduction_environment.json'
output.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
print(json.dumps(report, indent=2))
