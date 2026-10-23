# List fixtures (test data only)

`sdn.csv`, `alt.csv` and `add.csv` use the exact OFAC SDN legacy CSV layout (no header row,
`-0- ` for empty fields) so they exercise the real importer. **Every entry is fictional.** They
include the three names the pre-S2.3 code hardcoded (GLOBALREMIT, DARKFUND, TERRORFIN) so the
legacy behaviour stays covered, as test data only.

`pep.csv` is the generic PEP import format (header row; aliases separated by `;`), also fictional.

Never commit the full SDN file: production imports download it (`python -m scripts.import_lists`).
