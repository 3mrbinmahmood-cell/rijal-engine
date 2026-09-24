# Shamela Reader integration

`rijal-db-client.js` provides an opt-in, asynchronous client for the local
Rijal Engine service on port 8765. It does not modify the existing reader's
annotation storage or its three-book isnad logic.

The `shamela_v057/` overlay adds a separate **قاعدة الرجال الكاملة** view to
Shamela Reader V0.5.6. Rebuild the standalone reader ZIP with:

```sh
python rijal_database/reader_adapter/package_shamela_v057.py \
  Shamela_Reader_V0.5.6.zip Shamela_Reader_V0.5.7.zip
```

The builder checks the input reader, copies its bundled books and original
reader logic unchanged, overlays the new interface, and verifies the output
ZIP. The full-corpus view searches source entries even when optional identity
files are absent. To display reviewed/provisional identity status, dates, and
teacher/student clues, start the separate Rijal Engine package with
`--identity`, `--dates`, and `--graph` paths as documented in `../API.md`.
Those relationships remain source-backed review clues, not verified people.
