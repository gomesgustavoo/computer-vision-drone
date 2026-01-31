#!/bin/bash
# Install dependencies for DeepStream Python bindings and GStreamer
echo "Installing prerequisites..."
sudo apt-get update
sudo apt-get install -y \
    python3-gi python3-dev python3-gst-1.0 python3-numpy \
    libgstreamer1.0-0 gstreamer1.0-tools gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav libgstreamer-plugins-base1.0-dev \
    libgstrtspserver-1.0-0 libjansson4 libyaml-cpp-dev \
    libgstreamer-plugins-bad1.0-0 libsrtp2-1 libsrtp2-dev

echo "Note: Ensure NVIDIA DeepStream SDK is installed at /opt/nvidia/deepstream/deepstream"
echo "If 'pyds' is not found, you may need to install the python bindings from /opt/nvidia/deepstream/deepstream/sources/python"
