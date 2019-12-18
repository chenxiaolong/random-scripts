# Random Scripts

This repo contains random scripts that I use for various purposes.

### `convert-beat-saber-obs-recording.ps1`

Trims my Beat Saber game recordings from OBS (to the nearest H.264 GOP) and fixes audio sync issues caused by SteamVR's mirroring. I use TMPGEnc for lossless (minus starting and ending GOP) frame-perfect trimming for videos I keep.

Dependencies: `ffmpeg`