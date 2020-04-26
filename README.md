# Random Scripts

This repo contains random scripts that I use for various purposes.

### `convert-beat-saber-obs-recording.ps1`

Trims my Beat Saber game recordings from OBS to the nearest H.264 GOP. I use TMPGEnc for lossless (minus starting and ending GOP) frame-perfect trimming for the videos I keep.

Dependencies: `ffmpeg`

### `download-beat-saber-playlist.py`

Downloads all listed Beat Saber custom maps from a bplist (JSON) playlist file if they don't already exist.

Dependencies:

* Any valid handler for `beatsaver://` URIs (eg. [ModAssistant](https://github.com/Assistant/ModAssistant))
* Python modules from `requirements.txt`