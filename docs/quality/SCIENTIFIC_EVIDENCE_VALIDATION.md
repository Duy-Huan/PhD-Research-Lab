# Scientific evidence validation

The published [synthetic QA paper](../qa/evidence/2026-10-25/golden-verified/paper.pdf) is produced from an executed CPU experiment. It is not new scientific research and independent scientific review remains pending.

`scripts/toy_experiment.py` generates 128 sine samples with Gaussian noise sigma 0.25, seed 42, then applies a three-point smoothing filter. The measured noisy MSE is **0.05239628082235049**, and filtered MSE is **0.01861695929905821**. These values are read from outputs, not supplied by the model.

`scripts/verify_golden_thread.py` ingests an authored synthetic PDF with SHA-256 provenance, pins the CPU budget, asks Spark about source values, creates a code project, executes the actual sandbox process, reruns in a fresh subprocess and independently recomputes MSE from raw CSV using `math.fsum`. Both CSVs have SHA-256 `a349e0dd5122f8e042b58af02be0b8db2570c97404f192881e1b6e1a7ab130d0`.

The figure store renders actual measured series. The writer retains citation/figure lineage and Tectonic 0.17.0 compiles the PDF. PDFium rendered page 1 for visual inspection; the accepted page contains the actual MSE chart and fixture labels. Earlier placeholder exports were invalidated and remain in attempt history.

The [evidence directory](../qa/evidence/2026-10-25/golden-verified/) contains raw data, replay, metrics, figure, `.tex`, bibliography and PDF. [Manifest](../qa/evidence/2026-10-25/manifest.json) records file digests. Hash integrity alone is not replay or scientific verification. Legacy export bundles without an executable protocol explicitly remain unverified.
