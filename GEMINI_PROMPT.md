System Role: You are an expert NVIDIA DeepStream and Computer Vision engineer. You are acting as an autonomous code generator. Your goal is to produce a single, highly robust, and human-readable Python application.

Task: Create a Python application using NVIDIA DeepStream SDK bindings that:

Input: Exposes a UDP port to receive an incoming SRTP video stream.

Processing: Decodes the stream and applies a standard YOLO object detection model (via nvinfer) to identify objects.

Output: Displays the real-time video feed with bounding boxes drawn around detected objects in a GUI window on the same machine.

Target Environment: * OS: Windows 11 running WSL2 (Ubuntu).

Hardware: NVIDIA GPU (RTX series). nvidia-smi is already confirmed running and healthy in the environment.

Display: The environment supports WSLg (GUI output from WSL is visible on Windows).

Strict Constraints & Requirements:

Simplicity & Clarity: The solution must be a single, clean Python structure. Avoid complex multi-file architectures unless strictly necessary for config files.

No Loops/Interactions: Do not ask clarifying questions. Use your highest reasoning to infer the most standard, working configuration for this stack.

DeepStream Version: Assume DeepStream 6.4 or 7.0 (latest stable compatible with WSL2).

Network Logic: Explicitly handle the SRTP GStreamer pipeline string (srtpdec). You must define a default valid SRTP key/parameter set in the code as a placeholder or use decryption-key property logic if applicable, but ensure the port opening is valid for WSL2.

WSL2 Specifics:

Use nveglglessink if supported, but include a fallback comment for xvimagesink if EGL fails in WSLg.

Acknowledge that for the SRTP port to be accessible from outside the Windows machine, the user might need netsh forwarding, but your responsibility is ensuring the Python app binds correctly to 0.0.0.0 inside WSL.

Deliverables:

Prerequisite Check Command: A single CLI command to install the necessary DeepStream Python bindings and YOLO dependencies (e.g., pyds, deepstream-yolo-config).

Configuration Generation: Python code that automatically generates the required config_infer_primary_yolo.txt file if it doesn't exist, populated with standard YOLOv8 or YOLOv5 settings suitable for DeepStream.

Main Application (main.py):

Use the Gst and pyds libraries.

Construct the pipeline: udpsrc (SRTP) -> rtpdepay -> h264parse -> nvv4l2decoder -> nvstreammux -> nvinfer (YOLO) -> nvvideoconvert -> nvdsosd -> nveglglessink.

Includes a "Probe" function to parse metadata and print detection stats to the console (proof of inference).

Uses a try/except block to handle the GStreamer loop cleanly.

Context for Reasoning:

You must generate the exact GStreamer string or Python element construction sequence.

Assume the incoming stream is H.264 encoded over SRTP.

Provide a dummy SRTP key in the code for testing purposes (standard RFC 3711 base64 example).

Execute.
