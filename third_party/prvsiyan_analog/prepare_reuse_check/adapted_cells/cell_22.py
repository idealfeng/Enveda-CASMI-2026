'''## 8. Gated PubChem merge

PubChem-only candidates enter the main list only when there is no strong library match (`lib_max < 0.9`). When the PubChem fingerprint fit beats the best pool candidate by a wide margin, they take slots 2, 4, 6, 8 and 10. Otherwise they take slots 4, 8, 12, 16 and 20.
'''
