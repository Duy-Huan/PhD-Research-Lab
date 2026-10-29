# Proposed experiment design

Topic: 2d84fc5c-7cdc-4cae-9e60-744b5d3b6fda

Status: design only; no experiment or protocol has been run or approved here.

## Library and evidence

The topic library is empty: `library.search@1.0.0` with an empty query returned `total: 0` and `papers: []` (registry job `tj-5320ab757296963b6268`). Current-state and failure-memory queries returned no research records or record ids. There are therefore no HYPE-/EXP-/FAIL-/EVID-/CLM-/D… records to cite and no empirical results supporting this proposal. The choices below are proposed design parameters.

## One testable hypothesis

For a fixed clean, constant grayscale image with intensity 0.5, adding independent zero-mean Gaussian noise with standard deviation 0.10 and applying a fixed 3x3 box filter will yield a positive mean paired PSNR difference (filtered minus noisy input) across seeds 0, 1 and 2.

This deliberately narrow synthetic test assesses noise suppression in a flat image; it does not establish performance on textured or natural images, where smoothing may remove signal.

## Conditions and procedure for a future approved protocol

- Clean reference: a 256x256 grayscale floating-point image, all pixels 0.5; nominal intensity range [0, 1].
- Noise: independent Gaussian samples N(0, 0.10²), generated separately using NumPy Generator(PCG64(seed)); seeds exactly 0, 1 and 2. Add noise to the clean reference without clipping or quantization.
- Baseline: the noisy input itself, with no processing.
- Method: one pass of the fixed kernel K[i,j] = 1/9 for all nine entries of a 3x3 window. No tuning, training or repeated filtering.
- Pairing: for each seed, evaluate baseline and method using the identical noisy realization and clean reference.
- Boundary rule: use valid convolution and evaluate both conditions against the same central 254x254 reference region. Crop the baseline by one pixel on every edge; the filtered output already has that size.
- Arithmetic: float64 throughout; do not clip filtered output. Preserve the noise implementation and package versions in the future protocol.

## Metric and decision rule

For each condition and seed, compute MSE against the clean reference over the evaluated pixels, then PSNR = 10 log10(1² / MSE), in dB, using fixed peak/data_range = 1. If MSE is zero, report PSNR as +infinity and disclose that the paired comparison needs special handling.

Report each seed's baseline PSNR, filtered PSNR and paired difference ΔPSNR. The primary metric is the arithmetic mean of the three paired differences in dB. The stated hypothesis is supported for this predefined test if that mean is strictly greater than 0 dB, and is not supported if it is at most 0 dB. Report all three differences to expose seed variation; three seeds alone do not justify broad statistical or image-population claims.

## Unverified and researcher action

No images, noise, metrics or numerical outcomes have been generated. Neither implementation correctness nor the hypothesis has been verified. Before any execution, the researcher must review these proposed parameters and have the design implemented and approved as a PhD-Lab protocol; execution must occur through that approved protocol. No protocol approval or experiment record is claimed by this document.
