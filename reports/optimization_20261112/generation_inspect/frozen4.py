def locate_data_dir():
    candidates = [
        Path("/kaggle/input/competitions/enveda-CASMI26-molecule-id-mass-spectra"),
        Path("/kaggle/input/enveda-casmi26-molecule-id-mass-spectra"),
        Path("/kaggle/input/enveda-CASMI26-molecule-id-mass-spectra"),
        Path("data/raw"),
        Path("../data/raw"),
    ]
    for path in candidates:
        if all((path / name).exists() for name in ("train.parquet", "test.parquet", "sample_submission.csv")):
            return path.resolve()
    raise FileNotFoundError("Could not find train.parquet, test.parquet, and sample_submission.csv")


DATA = locate_data_dir()
TRAIN_PATH = DATA / "train.parquet"
TEST_PATH = Path(os.environ.get("CASMI_TEST_PATH", DATA / "test.parquet"))
SAMPLE_PATH = Path(os.environ.get("CASMI_SAMPLE_PATH", DATA / "sample_submission.csv"))