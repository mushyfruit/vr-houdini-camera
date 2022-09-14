# VR-Houdini-Camera
Houdini Utility to stream and record VR Input from HMD or Controllers to a viewport camera. Implements a slating system, SceneViewer overlay countdown, and playback of recorded clips to the viewport. Includes simple utility for transferring .bclip data over sockets on the local network.

## Installation
* Copy the "VR_Houdini_Camera.json" package file to $HOME/houdini19.5/packages and edit the path to point to root folder of VR Houdini Camera.

## Usage
* Record VR Input from HMD or Controllers directly to a Houdini Viewport Camera.
* Qt Viewport Overlays with countdown and recording overlay indicating shot length.
* Keep track of shots with Slate Names and Take Numbers.
* Options to playback last shot and load .bclip files from disk.
* Transmit recordings to other Houdini sessions on the local network in the Transmit tab.
* Stream camera position over local network sockets to Houdini Session.
