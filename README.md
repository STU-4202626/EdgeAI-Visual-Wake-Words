# EdgeAI - Visual Wake Words

**How does person detection perform across edge devices?**

> [!IMPORTANT]
> This repository preserves the Visual Wake Words experiments from the completed EdgeAI Honours project at commit `7d31a9c`. Historical models, implementations and results are retained together.

The workload evaluates a small image classifier that distinguishes **person** from **non-person**. It compares an x86 CPU, a dedicated GPU, a Raspberry Pi 5, an Android smartphone and an ESP32-S3 using classification measurements, workload inference time, throughput and estimated operational carbon emissions.

This is an **adapted experimental evaluation derived from MLPerf Tiny**, not an official MLPerf Tiny submission.

## Model and dataset

The benchmark uses **MobileNet V1**, with depthwise separable convolutions and a reduced width suitable for constrained devices. The retained model definition uses an initial eight filters, corresponding to the reference's 0.25 width setting, and two output classes.

[Visual Wake Words](https://github.com/mlcommons/tiny) derives a person/non-person classification task from COCO images. Inputs are **96 x 96 RGB**, resized as needed and normalized by `/255`. The evaluation contains **1,000 images: 500 person and 500 non-person**, using the MLPerf Tiny reference **80% top-1 accuracy target**.

The scripts select images using seed 42 and unsorted directory listings. This balances the classes, but does not establish an identical image subset across filesystems.

## Evaluated configurations

<table align="center">
  <thead>
    <tr><th>Device</th><th>Deployment configuration</th></tr>
  </thead>
  <tbody>
    <tr><td>AMD Ryzen 7 6800H</td><td>Full-precision TensorFlow; x86 CPU reference</td></tr>
    <tr><td>NVIDIA GeForce RTX 4090</td><td>Full-precision TensorFlow; RunPod GPU reference</td></tr>
    <tr><td>Raspberry Pi 5</td><td>Full-precision TensorFlow and INT8 LiteRT</td></tr>
    <tr><td>Samsung Galaxy S26 Ultra</td><td>INT8 LiteRT through tflite_runtime</td></tr>
    <tr><td>Waveshare ESP32-S3</td><td>INT8 TensorFlow Lite Micro; 240 MHz, 16 MB flash, 8 MB Octal PSRAM</td></tr>
  </tbody>
</table>

Full-precision TensorFlow constructs the retained `vww_model_updated.py` definition and loads `vww_96.h5` weights. The Pi INT8 and Android scripts use `vww_96_int8.tflite` through LiteRT. The ESP32-S3 runs the byte-identical embedded INT8 model through TensorFlow Lite Micro.

## Implementation and procedure

The procedure uses one warm-up and three measured runs. Each measured run repeats complete 1,000-image workloads until at least 30 seconds of elapsed prediction-loop time has been reached, completing its current repetition. Time and emissions are normalized to one complete workload. The ESP32-S3 uses accumulated device invocation time for this interval.

The CPU path loads, resizes and normalizes images inside its timed loop. GPU, Pi, Android and ESP paths prepare inputs before the model loop. This difference matters when interpreting CPU comparisons as inference performance.

The ESP host sends **27,648-byte INT8 image tensors at 921600 baud**. Firmware reserves a **1 MiB PSRAM arena** and returns two quantised outputs and device-side `Invoke()` time. Host preprocessing, serial transfers and the 500 ms command delay are excluded from reported ESP inference time and throughput.

The [MobileNet firmware documentation](MLPerf_Tiny/MLPerf_Tiny_ESP32-S3/training/visual_wake_words/firmware/README.md) records ESP-IDF **6.0.3**, TensorFlow Lite Micro component **1.4.0**, ESP-NN **1.3.2**, configuration and build/flash instructions.

> [!NOTE]
> Android and Raspberry Pi INT8 retain the historical output probability handling. Subsequent corrections have not been benchmarked again. Existing CSVs are historical measurements, not results of those corrected implementations.

## Recorded results

Time is for **all 1,000 images**, throughput is images/s, and emissions are estimated kgCO2e per workload. Accuracy, workload time and estimated emissions average the three measured runs, excluding warm-up. Throughput is the workload sample count divided by the mean recorded workload time. All six configurations met the 80% target.

<table align="center">
  <thead>
    <tr><th>Configuration</th><th>Accuracy (%)</th><th>Time / workload (s)</th><th>Throughput (images/s)</th><th>Estimated emissions (kgCO2e)</th></tr>
  </thead>
  <tbody>
    <tr><td>AMD Ryzen 7 6800H</td><td>86.3</td><td>57.181</td><td>17.49</td><td>8.702e-05</td></tr>
    <tr><td>NVIDIA GeForce RTX 4090</td><td>86.7</td><td>42.586</td><td>23.48</td><td>4.918e-04</td></tr>
    <tr><td>Raspberry Pi 5 - full precision</td><td>85.9</td><td>79.729</td><td>12.54</td><td>3.943e-05</td></tr>
    <tr><td>Raspberry Pi 5 - INT8</td><td>85.5</td><td>1.128</td><td>886.52</td><td>6.087e-07</td></tr>
    <tr><td>Samsung Galaxy S26 Ultra</td><td>88.2</td><td>0.103</td><td>9708.74</td><td>3.174e-09</td></tr>
    <tr><td>ESP32-S3</td><td>85.8</td><td>77.249</td><td>12.95</td><td>4.405e-06</td></tr>
  </tbody>
</table>

The [six-record summary](historical-results/MLPerf_Tiny/mlperf_tiny_all_devices_summary.csv) retains precision, recall, F1-score, ROC-AUC, repetitions and pass status. [Historical result folders](historical-results/MLPerf_Tiny/) preserve the raw CSVs, prediction labels, confusion matrices, ROC curves and available estimation logs.

Raspberry Pi INT8 throughput is approximately **70.7x** the displayed full-precision Pi throughput. This is a comparison of the recorded implementations. Accuracy varies between configurations, and image-selection, preprocessing and output-handling differences prevent attributing every difference to numerical precision alone.

## Installation and execution

### Python environment

Install the common analysis and image packages from the repository root:

```text
python -m pip install -r requirements/base.txt
```

Full-precision CPU/GPU/Pi additionally need a compatible **TensorFlow/Keras 2** build and `requirements/tensorflow.txt`. Android/Pi INT8 need `requirements/litert.txt` and a compatible `tflite-runtime` wheel for their platform. The ESP host uses `requirements/esp32-host.txt` and does not require TensorFlow for inference.

The package lists are inferred from imports and do not lock the original environments. TensorFlow, CUDA, LiteRT wheel availability and Android execution-environment setup must be resolved for the target system. A fresh installation has not been tested. The GPU script requires a visible GPU; CodeCarbon settings alone do not establish runtime placement.

### Prepare Visual Wake Words

The MLCommons reference preparation script identifies a prepared 96 x 96 dataset archive from Silicon Labs. To obtain and extract the dataset from a workload directory:

```sh
wget https://www.silabs.com/public/files/github/machine_learning/benchmarks/datasets/vw_coco2014_96.tar.gz
tar -xvf vw_coco2014_96.tar.gz
```

> [!NOTE]
> The reference dataset host returned HTTP 403 to an availability HEAD request during preparation. Download access has not been verified. If the host rejects access, obtain the prepared archive from the provider or use a previously obtained local copy with the required layout.

These are dataset-preparation instructions, not commands executed during extraction. The [upstream preparation source](https://github.com/mlcommons/tiny/blob/1afd2c9820f795965a6134facd0b4dfae41ef23f/benchmark/training/visual_wake_words/download_and_train_vww.sh) also contains training and conversion commands; those are not required to benchmark the supplied models.

Each platform's `training/visual_wake_words/` working directory must provide:

```text
vw_coco2014_96/
    person/       # at least 500 images
    non_person/   # at least 500 images
trained_models/
```

Dataset-specific terms remain applicable. Raw images and archives are excluded. Preserve the intended dataset, label mapping and directory ordering when comparing future experiments; the same random seed alone cannot reconstruct the historical selection.

### Run a configuration

From the selected platform's `training/visual_wake_words/` directory, execute:

<table align="center">
  <thead>
    <tr><th>Platform directory under MLPerf_Tiny/</th><th>Script in training/visual_wake_words/</th></tr>
  </thead>
  <tbody>
    <tr><td>MLPerf_Tiny_PC_CPU</td><td>mlperf_visual_wake_words_CPU_bench.py</td></tr>
    <tr><td>MLPerf_Tiny_PC_GPU</td><td>mlperf_visual_wake_words_RunPod_GPU.py</td></tr>
    <tr><td>MLPerf_Tiny_RaspberryPi5</td><td>mlperf_visual_wake_words_Pi5_full.py or mlperf_visual_wake_words_Pi5_quant.py</td></tr>
    <tr><td>MLPerf_Tiny_Android</td><td>mlperf_visual_wake_words_Android_bench.py</td></tr>
    <tr><td>MLPerf_Tiny_ESP32-S3</td><td>mlperf_visual_wake_words_ESP32S3_bench.py</td></tr>
  </tbody>
</table>

For example, from the Raspberry Pi workload directory:

```text
python mlperf_visual_wake_words_Pi5_quant.py
```

For ESP32-S3, build and flash the matching MobileNet project using its firmware README before running the host. The historical host uses `COM8`; select the actual port for a future run and close any serial monitor. `PING/PONG` confirms communication without identifying the flashed model. No build, flash or hardware execution was performed during extraction.

Models, images and outputs use paths relative to the workload working directory. The retained parent `training/results_helper.py` and ESP `training/esp32_energy_helper.py` satisfy shared imports. New outputs use ignored `results/` directories, or Pi `results_full/` and `results_quant/`; historical outputs are kept separately.

To compile **new** outputs, from `MLPerf_Tiny/` run `python compile_results.py MLPerf_Tiny_PC_CPU` for each platform folder, followed by `python compile_all_devices.py` after all five summaries exist. The compiler discovers only Visual Wake Words, without reading or replacing `historical-results/`.

## Measurement limitations and reproducibility

The CPU, GPU, Raspberry Pi and Android record elapsed Python prediction-loop time per complete workload, including runtime and output handling. The ESP32-S3 sums device-side `Invoke()` durations. These timing scopes differ; the tables do not measure end-to-end application latency.

CodeCarbon provides software-based energy and carbon estimates on the four larger platforms. Logs use different regional carbon intensities and power estimates, including a 42.5 W CPU fallback on Android. The ESP32-S3 helper applies **0.29007 W** and **0.707686 kgCO2e/kWh** to device invocation time. Neither method directly measures whole-device or host electricity consumption.

Python package versions, delegates and operating-system settings are not fully locked. CPU/GPU labels describe the reported experimental configurations; `gpu_ids=[]` configures CodeCarbon and does not itself force TensorFlow placement. The LiteRT scripts import `tflite_runtime.interpreter.Interpreter`; no explicit Android NPU delegate is configured. LiteRT denotes the TensorFlow Lite runtime used by these INT8 scripts, while TensorFlow Lite Micro executes the embedded model on the microcontroller.

See [result provenance](MLPerf_Tiny/RESULTS_PROVENANCE.md) and [static verification](STATIC_VERIFICATION.md). Extraction validation checks syntax, artifacts, links and recorded values. It does not establish a fresh environment, clean firmware build or successful new inference.

## Attribution

This workload derives from [MLCommons MLPerf Tiny](https://github.com/mlcommons/tiny). The [Apache 2.0 licence](MLPerf_Tiny/LICENSE.md), original source notices and [focused attribution](MLPerf_Tiny/ATTRIBUTION.md) are retained. Dataset and downloaded dependency terms apply separately.

This is a standalone extraction of **EdgeAI: Performance Analysis of Edge Nodes for AI Tasks**, a 2026 BSc Honours Computer Science project. See the [original Honours project](https://github.com/STU-4202626/EdgeAI-Performance-Analysis/tree/7d31a9c273d1e4b088faed55508907e7ef04c3d3) for the complete comparison and research context.
