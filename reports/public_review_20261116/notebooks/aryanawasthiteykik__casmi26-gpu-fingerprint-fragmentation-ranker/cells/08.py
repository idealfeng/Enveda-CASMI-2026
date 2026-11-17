from pipeline import run
t = time.time()
sub = run(DATA / 'train.parquet', DATA / 'test.parquet', '/kaggle/working/structures.parquet',
          '/kaggle/working/fps.npy', V3 / 'fpnet_v3h.pt', PUBCHEM, POP, gate=0.7,
          hidden=CFG['hidden'], depth=CFG['depth'], ranker_path=V3 / 'learned_ranker_v3.txt')
sub.to_csv('submission.csv', index=False)
print(sub.shape, f'{time.time() - t:.0f}s')
sub.head()