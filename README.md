# VR-Houdini-Camera

Houdini 22 utility to stream and record VR HMD/controller input to a viewport camera. It includes slate and recording overlays, clip playback, and local-network `.bclip` transfer.

This project utilizes cmbrun's amazing [pyopenxr](https://github.com/cmbruns/pyopenxr) and [pyopenvr](https://github.com/cmbruns/pyopenvr) libraries.

Requires Houdini 22 (Python 3.11+) and PySide6. Tested with an HTC Vive HMD and Vive Tracker.

## Example Footage

https://user-images.githubusercontent.com/73495888/190064860-77a33d7d-43a3-450f-9cdf-5c366252e007.mp4

## Installation

1. Copy `VR_Houdini_Camera.json` to `$HOME/houdini22.0/packages` and set `VR_CAM` to this repository's absolute path.
2. Install dependencies with Houdini's Python: `hython -m pip install -r /path/to/VR-Houdini-Camera/requirements.txt`.
3. Enable and track your VR devices.

The package adds the repository root to Houdini's path, registering both its Python scripts and `viewer_states/follow_focus.py`.

## Usage

Choose **VR Camera - Record and Transmit** from the Windows menu. Record VR input directly to a viewport camera, label takes with slates, replay clips, or send recordings and camera positions to another local Houdini session.

Tip: disable SteamVR Home for improved performance (enable SteamVR Developer Settings first).
