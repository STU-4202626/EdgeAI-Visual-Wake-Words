# Source Attribution

This standalone Visual Wake Words extraction contains reference models and adapted source from [MLCommons MLPerf Tiny](https://github.com/mlcommons/tiny), through the [historical EdgeAI baseline](https://github.com/STU-4202626/EdgeAI-Performance-Analysis/tree/7d31a9c273d1e4b088faed55508907e7ef04c3d3). The complete [Apache License 2.0](LICENSE.md) is an unchanged copy of `Original_MlPerf_tiny/tiny/LICENSE.md` from the local reference checkout (upstream revision `1afd2c9820f795965a6134facd0b4dfae41ef23f`).

MLCommons, TensorFlow Authors, SiliconLabs and EEMBC notices appearing in selected source files are preserved. Existing prominent EdgeAI adaptation comments remain intact. Copying to another directory does not assert a change to that source file.

The ESP32-S3 firmware derives in part from TensorFlow Lite Micro and [Espressif's Hello World foundation](https://github.com/espressif/esp-tflite-micro/tree/master/examples/hello_world). Workload-specific UART transport, PSRAM allocation, operators and invocation timing were developed for EdgeAI; the retained headers identify these adaptations. Component licences accompany dependencies restored by ESP-IDF, rather than downloaded generated directories in this extraction.

Benchmark scripts, model artifacts, firmware source and raw historical outputs other than the privacy-reduced CodeCarbon `emissions.csv` files are byte-identical to the pinned source Git blobs. CodeCarbon public copies preserve all retained values and row order; [result provenance](RESULTS_PROVENANCE.md) records the removed geographical columns. `compile_results.py` has a prominent standalone modification notice and restricts workload discovery to `visual_wake_words`; its result calculations are unchanged. `compile_all_devices.py` is unchanged. These utilities operate on future output directories and were not run to regenerate the historical results.

New standalone documentation, manifests and validation tooling are identified as extraction additions. This attribution does not automatically relicense independently developed EdgeAI helpers, compilation utilities, documentation or results. Dataset terms and citations apply separately.

MLCommons requests citation of the MLPerf Tiny Benchmark paper when its materials are used academically; see the [upstream citation](https://github.com/mlcommons/tiny). These are adapted experimental evaluations, not official MLPerf Tiny submissions.
