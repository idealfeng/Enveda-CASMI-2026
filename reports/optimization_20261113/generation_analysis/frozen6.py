try:
    rows = []
    for name, path, unit in (('train.parquet', TRAIN_PATH, 'a labelled spectrum'),
                             ('test.parquet', TEST_PATH, 'an unlabelled spectrum')):
        meta = pq.ParquetFile(path).metadata
        rows.append((name, unit, meta.num_rows, meta.num_columns))
    sub = pd.read_csv(SAMPLE_PATH, usecols=['molecule_id'])
    rows.append(('sample_submission.csv', 'a molecule to answer', len(sub), 2))
    display(pd.DataFrame(rows, columns=['file', 'one row is', 'rows', 'columns']).style.hide(axis='index')
            .format({'rows': '{:,}'}))
    n_train = pq.read_table(TRAIN_PATH, columns=['inchikey14']).column('inchikey14').to_pandas().nunique()
    n_test = pq.read_table(TEST_PATH, columns=['molecule_id']).column('molecule_id').to_pandas().nunique()
    print(f'training structures (distinct inchikey14): {n_train:,}; test molecules: {n_test:,}')
    del sub
except Exception as exc:
    print('competition file table unavailable:', type(exc).__name__, exc)