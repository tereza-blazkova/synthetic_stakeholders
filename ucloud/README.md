# Running the large-tier study on UCloud

Everything runs with one script, `ucloud/run_ucloud.sh`, in three stages. You
start each stage; I check the results in between. Nothing needs API keys, and no
personal data are involved (the application says N/A).

## 0. Upload the project (once)

1. In UCloud, open **Files** and upload `synthetic_stakeholders_ucloud.zip`
   (in the project folder on your laptop; built by `ucloud/make_upload.sh`).
2. Unzip it in UCloud (right-click → Extract), giving a folder
   `synthetic_stakeholders/`.

## 1. Start a job

- App: a terminal app with a GPU, e.g. **Terminal (Ubuntu)** or **Coder** / **JupyterLab**.
- Machine: **1× NVIDIA B200** (the u-gpu product from the grant).
- Folders: mount the `synthetic_stakeholders/` folder.
- Time: 12 hours for the setup + pilot session; extend or restart for the main runs
  (restarting is safe: finished runs are skipped).

Open the terminal and go to the project:

```bash
cd /work/synthetic_stakeholders      # adjust to where UCloud mounted the folder
```

## 2. Setup (~15–30 min, mostly the 50 GB model download)

```bash
bash ucloud/run_ucloud.sh setup
```

It installs Ollama 0.30.11 (same version as the laptop) into your home folder,
creates a Python environment, downloads the three models, writes their digests to
`ucloud/digests.txt`, and runs the test suite. The last line should be `setup done`.

## 3. Pilot (~1 h; I check before the main runs)

```bash
bash ucloud/run_ucloud.sh pilot
```

Runs one lite and one full workshop per family, all three families in parallel.
At the end it writes `results_pilot_<date>.tgz` in the project folder.
**Download that file and put it in the project folder on your laptop**, then tell
me. I check timing, answer rates and transcripts (~15 min) and say go / fix.

## 4. Main runs

```bash
bash ucloud/run_ucloud.sh main 1-10
```

Runs 1–10 of both protocols for all three families. Order inside each family:
lite 1, full 1, lite 2, full 2, ... so if you have to stop early, every family
and protocol has the same number of finished runs. Download
`results_main_1-10_<date>.tgz` when it finishes. If there is time:

```bash
bash ucloud/run_ucloud.sh main 11-20
```

## Checking progress (any time, in a second terminal tab)

```bash
bash ucloud/run_ucloud.sh status
```

## If something goes wrong

- **The job ended or was cancelled**: start a new job, `cd` to the folder, run the
  same command again. Finished runs are skipped; a half-finished workshop is not
  scored (it has no `run_meta.json`). Delete its folder before restarting it.
- **`ollama install failed`**: the job image may lack `curl` or `tar`; send me the
  output. Alternative: choose an app image that already has Ollama, then rerun `setup`.
- **Out of GPU memory** (in `runs/_logs/ollama_serve.log`): unlikely with 192 GB, but
  setting `OLLAMA_MAX_LOADED_MODELS=1` in the script and running the families one at a
  time works too (slower).
