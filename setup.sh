#!/bin/bash
set -e

echo "=================================================="
echo "   DeepStream Drone Pipeline - Setup Script"
echo "=================================================="

# 1. System Dependencies
echo "[1/3] Installing System Dependencies..."
sudo apt-get update
sudo apt-get install -y \
    python3-gi python3-dev python3-gst-1.0 python3-numpy \
    libgstreamer1.0-0 gstreamer1.0-tools gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav libgstreamer-plugins-base1.0-dev \
    libgstrtspserver-1.0-0 libjansson4 libyaml-cpp-dev \
    libgstreamer-plugins-bad1.0-0 libsrtp2-1 libsrtp2-dev \
    wget tar

# 2. MediaMTX Setup (RTMP Server)
echo "[2/3] Setting up MediaMTX (RTMP Server)..."
MEDIAMTX_DIR="mediamtx"
if [ -d "$MEDIAMTX_DIR" ]; then
    echo "   MediaMTX already installed in ./$MEDIAMTX_DIR"
else
    mkdir -p "$MEDIAMTX_DIR"
    echo "   Downloading MediaMTX v1.6.0..."
    wget -q https://github.com/bluenviron/mediamtx/releases/download/v1.6.0/mediamtx_v1.6.0_linux_amd64.tar.gz -O mediamtx.tar.gz
    tar -xf mediamtx.tar.gz -C "$MEDIAMTX_DIR"
    rm mediamtx.tar.gz
    echo "   MediaMTX installed successfully."
fi

# 3. DeepStream Python Bindings Check
echo "[3/3] Checking DeepStream Environment..."

if python3 -c "import pyds" 2>/dev/null; then
    echo "   [OK] DeepStream Python bindings ('pyds') are detected."
else
    echo "   [WARNING] 'pyds' library not found!"
    echo "   To install it, you usually need to run the bindings installer included with DeepStream:"
    echo ""
    echo "   cd /opt/nvidia/deepstream/deepstream/sources/deepstream_python_apps/bindings"
    echo "   mkdir build && cd build"
    echo "   cmake .."
    echo "   make"
    echo "   pip3 install ./pyds-*.whl"
    echo ""
    echo "   Ensure you have cloned https://github.com/NVIDIA-AI-IOT/deepstream_python_apps"
fi

echo "=================================================="
echo "   Setup Complete!"
echo "   Start the RTMP Server:  cd mediamtx && ./mediamtx"
echo "   Start the Pipeline:     python3 main.py"
echo "=================================================="
