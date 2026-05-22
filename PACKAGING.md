# Packaging Extractor with PyInstaller

This guide describes how to bundle the application using PyInstaller on Windows. It supports both **Online** and **Offline** model loading strategies.

---

## Prerequisites

First, make sure PyInstaller is installed in your virtual environment:

```bash
pip install pyinstaller
```

---

## Strategy A: Online Mode (Lightweight Executable)

In this mode, the model files are **not** bundled inside the final executable folder.
* **Pros**: The compiled directory size is small (~250 MB).
* **Cons**: The first time the packaged app is run on a new computer, it requires an internet connection to download the layout model (~1.5 GB). Subsequent runs are instant and work 100% offline.

### Packaging Command:
Run PyInstaller using the prepared `app.spec` file:

```bash
pyinstaller --noconfirm app.spec
```

The output will be created inside the `dist/Extractor/` folder.

---

## Strategy B: Offline Mode (Fully Self-Contained Executable)

In this mode, the pre-downloaded layout detection models already on your computer are packaged directly inside the executable folder.
* **Pros**: The application is 100% self-contained and works completely offline immediately on the very first run on any new computer (no downloading needed).
* **Cons**: The final compiled folder size will be larger (around 1.5 - 2.0 GB).

### Setup Steps:
1. Create a `models` folder in the root directory of this project.
2. Locate the `.paddlex` folder on your computer. By default, it is at:
   `C:\Users\<YourUsername>\.paddlex`
3. **Copy** that `.paddlex` directory into the new `models` folder, so you have:
   `models/.paddlex/official_models/...`
4. Open the `app.spec` file in a text editor, scroll to the **`datas`** block, and **uncomment** this line:
   ```python
   datas.append(('models/.paddlex', 'models/.paddlex'))
   ```
5. Run the packaging command:
   ```bash
   pyinstaller --noconfirm app.spec
   ```

The output will be created inside the `dist/Extractor/` folder.

---

## Distribution

Once built, you can compress the `dist/Extractor/` folder into a `.zip` file. The end user can simply unzip the file and double-click `Extractor.exe` inside the folder to run the application (no python installation required).
