
# 🚀 Universal App & Node Editor Builder

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/)
[![PyQt5](https://img.shields.io/badge/PyQt5-GUI-green.svg)](https://pypi.org/project/PyQt5/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Author](https://img.shields.io/badge/Author-Akash%20Kumar-orange.svg)](mailto:earthlyakash@gmail.com)

**An advanced, dual-mode visual software development environment for building desktop apps and ComfyUI-inspired AI image processing pipelines.**

</div>

---

## 📖 Table of Contents
- [✨ Overview](#-overview)
- [🌟 Key Features](#-key-features)
- [🎯 Use Cases](#-use-cases)
- [🛠️ Project Structure](#️-project-structure)
- [📦 Dependencies](#-dependencies)
- [⚙️ Installation & Setup](#️-installation--setup)
- [🚀 How to Use](#-how-to-use)
- [👤 Author & Contact](#-author--contact)

---

## ✨ Overview

**Universal App & Node Editor Builder** is a powerful desktop software designed to bridge the gap between visual programming and Python code execution. It features a **Dual-Mode Workspace**:
1. **App Builder Mode:** Drag-and-drop UI elements (buttons, inputs, consoles, text editors) to design custom desktop apps and compile them into standalone `.exe` binaries using PyInstaller.
2. **Node Image Editor Mode:** A ComfyUI-inspired canvas where you can connect images, lists, constructor engines, and AI/custom processing nodes with visual wires.

---

## 🌟 Key Features

* **🔄 Dual-Mode Workspace:** Seamlessly toggle between designing user interfaces and building modular node-based data flow graphs.
* **🧠 Advanced AI Integration:** Built-in hooks and execution pipelines for heavy machine learning and computer vision models (Cloth Segmentation, Depth Anything, LaMa Inpainting, GFPGAN, Real-ESRGAN).
* **🔍 Dynamic AST Code Parsing:** Automatically scans backend files (`functions.py`, `ai_functions.py`, `customCode.py`) to populate nodes, dropdowns, and documentation dynamically.
* **🛠️ Universal Path & Macro Builder:** Dynamically map input/output routes using powerful tags like `{current_name}`, `{original_ext}`, `{preserve_structure}`, and auto-incrementing counters.
* **📦 One-Click EXE Publishing:** Compile your visual projects into standalone Windows executable applications automatically.
* **⚡ Non-Blocking Execution:** Background worker threads ensure that heavy AI processing or bulk image loops never freeze the UI.

---

## 🎯 Use Cases

* **Batch AI Image Pipelines:** Process directories of images in bulk (background removal, upscaling, depth map generation, and colorization) with real-time logging.
* **Custom Desktop Utility Creation:** Quickly build standalone GUI tools complete with input fields, file dialogs, and custom actions without writing boilerplate code.
* **Visual Logic Scripting:** Chain custom Python functions, conditional file filters, and directory loops using interactive wires and property inspectors.

---

## 🛠️ Project Structure

```text
├── ui.py              # Main application window, node canvas, and App Builder engine
├── functions.py       # Standard image processing and file utility functions
├── ai_functions.py    # Deep learning & AI model wrappers (ONNX/PyTorch)
└── customCode.py      # User-defined custom global script storage
```

---

## 📦 Dependencies

Ensure your environment includes the required libraries before running the project:

* **Python** 3.8 or higher
* **PyQt5** (UI Framework)
* **OpenCV** (`opencv-python`)
* **NumPy**
* **Pillow** (`Pillow`)
* **PyTorch & Torchvision** (For AI pipelines)
* **ONNXRuntime** (`onnxruntime`)
* **Transformers & Hugging Face Hub** (For modern depth/AI models)
* **PyInstaller** (Optional, for compiling `.exe` builds)

---

## ⚙️ Installation & Setup

1. **Clone or Download** the repository files (`ui.py`, `functions.py`, `ai_functions.py`, `customCode.py`) into your local project workspace.
2. **Open Terminal / Command Prompt** in the project directory.
3. **Install Dependencies** using pip:
   ```bash
   pip install PyQt5 opencv-python numpy pillow torch torchvision onnxruntime transformers realesrgan gfpgan
   ```
4. **Launch the Application:**
   ```bash
   python ui.py
   ```

---

## 🚀 How to Use

1. **App Builder Mode:** Click **"Start Build App"**, drop buttons and input fields onto the window, link them to backend functions using the property panel, and click **"Publish App (EXE)"**.
2. **Node Image Editor Mode:** Click **"Node Image Editor"**, drop an **Image Node** or **Batch List Node**, connect it to a **Constructor Engine** and a processing node, then click **"Run & Process"**.
3. **Shortcuts:**
   - `Ctrl + F`: Open Universal Search & Add Palette
   - `Ctrl + C / Ctrl + V`: Copy & Paste Elements/Nodes
   - `Ctrl + S`: Save Project Workspace

---

## 👤 Author & Contact

* **Author:** Akash Kumar
* **Email:** [earthlyakash@gmail.com](mailto:earthlyakash@gmail.com)
