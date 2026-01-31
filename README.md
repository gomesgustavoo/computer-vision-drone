# DeepStream Drone Surveillance Pipeline

![DeepStream Version](https://img.shields.io/badge/NVIDIA%20DeepStream-6.4%2B-green)
![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![License](https://img.shields.io/badge/License-MIT-grey)
![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20WSL2-orange)

This project implements a production-grade, hardware-accelerated computer vision pipeline designed to ingest secure video feeds (SRTP) from DJI Enterprise drones. It leverages the NVIDIA DeepStream SDK to perform real-time object detection with near-zero latency using the `pyds` bindings.

The application allows for direct stream ingestion, hardware decoding (NVDEC), batch inference (TensorRT), and on-screen display rendering without CPU bottlenecks.

## System Architecture

The pipeline is constructed to minimize memory copies between host and device. Video data remains in GPU VRAM (NvBufSurface) throughout the entire lifecycle—from decoding to inference and rendering.

```mermaid
graph LR
    DJI[DJI Drone / SRTP Source] -->|UDP H.264| NET[Network Interface]
    NET -->|SRTP| G1[udpsrc]
    G1 -->|Depay/Parse| G2[nvv4l2decoder]
    G2 -->|NV12 Surface| G3[nvstreammux]
    G3 -->|Batch Buffer| G4[nvinfer (YOLOv8)]
    G4 -->|Meta Attached| G5[nvdsosd]
    G5 -->|Composited Output| G6[nveglglessink]
    
    subgraph Host
    DJI
    NET
    end

    subgraph "NVIDIA GPU (VRAM)"
    G2
    G3
    G4
    G5
    end
```

## Technical Highlights

*   **Zero-Copy Pipeline:** Utilizes NVIDIA's unified memory architecture. The H.264 stream is decoded directly into GPU memory, avoiding expensive PCIe transfers.
*   **SRTP Decryption:** Implements RFC 3711 compliant decryption for secure video transmission, common in enterprise drone deployments.
*   **TensorRT Inference:** Uses `nvinfer` to execute YOLO models optimized for FP16/INT8 precision.
*   **WSL2 Integration:** Optimized for Windows Subsystem for Linux with direct D3D12 interop via `nveglglessink` for native-like performance on Windows hosts.

## DJI Drone Integration

This application is designed to act as the ground station sink for DJI drones broadcasting over SRTP.

1.  **Network Topology:** Ensure the drone controller or relay application targets the host IP.
2.  **Port Forwarding (WSL2):** If running on WSL2, the UDP traffic must be bridged from the Windows host to the Linux instance.
    ```powershell
    # Windows PowerShell (Admin)
    netsh interface portproxy add v4tov4 listenport=5000 listenaddress=0.0.0.0 connectport=5000 connectaddress=$(wsl hostname -I)
    ```

## Installation

### Prerequisites
*   NVIDIA Driver 535+
*   NVIDIA DeepStream SDK 6.4 or 7.0
*   GStreamer 1.16+
*   Python 3.8+ with GObject Introspection

### Setup
Run the initialization script to pull dependencies and configure the environment variables:

```bash
./setup.sh
```

## Usage

### 1. Model Configuration
The application automatically generates a `config_infer_primary_yolo.txt` on first run. For production, replace the placeholder paths with your compiled TensorRT engine file:

```ini
[property]
model-engine-file=./models/yolov8s.engine
```

### 2. Execution
Launch the pipeline. The application will bind to `0.0.0.0:5000` and await the incoming SRTP stream.

```bash
python3 main.py
```

### 3. Simulation
To validate the pipeline without a physical drone, simulate an incoming SRTP stream using the local loopback:

```bash
gst-launch-1.0 videotestsrc is-live=true ! video/x-raw,width=1920,height=1080 ! \
    x264enc speed-preset=ultrafast tune=zerolatency ! rtph264pay ! \
    srtpenc key="000102030405060708090a0b0c0d0e0f000102030405060708090a0b0c0d" \
    rtp-cipher="aes-128-icm" rtp-auth="hmac-sha1-80" ! \
    udpsink host=127.0.0.1 port=5000 sync=false
```

## Performance Metrics

| Resolution | Model | FPS (RTX 3080) | Latency |
|------------|-------|----------------|---------|
| 1080p      | YOLOv8s | 85+ | < 30ms |
| 4K         | YOLOv8s | 45+ | < 50ms |

*Metrics are estimated based on standard DeepStream reference benchmarks.*

## License

MIT License. See [LICENSE](LICENSE) for details.