#!/usr/bin/env python3
import sys
import os
import gi
import time

gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

# Try to import pyds, but allow running without it for pipeline testing (though essential for DeepStream logic)
try:
    import pyds
except ImportError:
    print("WARNING: 'pyds' library not found. DeepStream bindings are missing.")
    print("Ensure you have installed the DeepStream SDK python bindings.")

# Constants
SRTP_PORT = 5000
YOLO_CONFIG_FILE = "config_infer_primary_yolo.txt"
# Standard RFC 3711 test key (16 bytes key + 14 bytes salt = 30 bytes, base64 encoded)
# Key: 0x00...0F, Salt: 0x00...0D
# Base64 for 30 bytes of 0x00 is 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
# Let's use a standard test key for SRTP.
# "Master Key" (16 bytes) + "Master Salt" (14 bytes)
DEFAULT_SRTP_KEY_BYTES = b'\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f' \
                         b'\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d'

def generate_yolo_config():
    """Generates a standard YOLOv8 configuration file for DeepStream if it doesn't exist."""
    if os.path.exists(YOLO_CONFIG_FILE):
        print(f"Configuration file {YOLO_CONFIG_FILE} already exists.")
        return

    config_content = """
[property]
gpu-id=0
net-scale-factor=0.0039215697906911373
model-color-format=0
custom-network-config=yolov8s.cfg
model-file=yolov8s.wts
# Ideally use the engine file for production
# model-engine-file=model_b1_gpu0_fp32.engine
# Setup for YOLO usually requires the custom parse function or lib
# For standard DeepStream YOLO usage:
network-type=0
is-classifier=0
# batch-size should match nvstreammux
batch-size=1
# 0=FP32, 1=INT8, 2=FP16
network-mode=2
num-detected-classes=80
interval=0
gie-unique-id=1
process-mode=1
network-type=0
cluster-mode=2
maintain-aspect-ratio=1
symmetric-padding=1
# Library for parsing YOLO outputs (standard for deepstream-yolo)
# parse-bbox-func-name=NvDsInferParseCustomYolo
# custom-lib-path=libnvdsinfer_custom_impl_Yolo.so

[class-attrs-all]
pre-cluster-threshold=0.2
"""
    with open(YOLO_CONFIG_FILE, "w") as f:
        f.write(config_content)
    print(f"Generated {YOLO_CONFIG_FILE} with standard YOLO settings.")

def srtp_request_key_callback(gst_srtp_dec, key_id, user_data):
    """
    Callback for srtpdec 'request-key' signal.
    Provides the SRTP parameters.
    """
    print(f"SRTP Key requested for Key ID: {key_id}")
    
    # Create a Gst.Caps for the key
    # Standard minimal SRTP caps
    srtp_caps = Gst.Caps.from_string(
        "application/x-srtp, "
        "srtp-key=(buffer)000102030405060708090a0b0c0d0e0f000102030405060708090a0b0c0d, "
        "srtp-cipher=(string)aes-128-icm, "
        "srtp-auth=(string)hmac-sha1-80, "
        "srtp-auth-tag-len=(int)80, "
        "srtp-cipher-key-len=(int)128"
    )
    return srtp_caps

def osd_sink_pad_buffer_probe(pad, info, u_data):
    """
    Probe to extract metadata and print detection info.
    """
    gst_buffer = info.get_buffer()
    if not gst_buffer:
        print("Unable to get GstBuffer")
        return Gst.PadProbeReturn.OK

    # Retrieve batch metadata from the gst_buffer
    # Note: verify pyds is available
    if 'pyds' not in sys.modules:
        return Gst.PadProbeReturn.OK

    batch_meta = pyds.gst_buffer_get_nvds_batch_meta(hash(gst_buffer))
    l_frame = batch_meta.frame_meta_list
    
    while l_frame is not None:
        try:
            frame_meta = pyds.NvDsFrameMeta.cast(l_frame.data)
        except StopIteration:
            break

        frame_number = frame_meta.frame_num
        num_rects = frame_meta.num_obj_meta
        
        # Print only every 30 frames to avoid spamming console
        if frame_number % 30 == 0:
            print(f"Frame Number={frame_number} Number of Objects={num_rects}")
            
            l_obj = frame_meta.obj_meta_list
            while l_obj is not None:
                try:
                    obj_meta = pyds.NvDsObjectMeta.cast(l_obj.data)
                    print(f"  Object: {obj_meta.obj_label} | Confidence: {obj_meta.confidence:.2f} | "
                          f"BBox: {obj_meta.rect_params.left:.0f}, {obj_meta.rect_params.top:.0f}, "
                          f"{obj_meta.rect_params.width:.0f}x{obj_meta.rect_params.height:.0f}")
                except StopIteration:
                    break
                try:
                    l_obj = l_obj.next
                except StopIteration:
                    break

        try:
            l_frame = l_frame.next
        except StopIteration:
            break
            
    return Gst.PadProbeReturn.OK

def main():
    # 1. Initialize GStreamer
    Gst.init(None)

    # 2. Generate Config
    generate_yolo_config()

    # 3. Create Pipeline
    pipeline = Gst.Pipeline()
    if not pipeline:
        sys.stderr.write(" Unable to create Pipeline \n")
        return

    # 4. Create Elements
    # Source: UDP -> SRTP
    udpsrc = Gst.ElementFactory.make("udpsrc", "udp-source")
    srtpdec = Gst.ElementFactory.make("srtpdec", "srtp-decoder")
    rtpdepay = Gst.ElementFactory.make("rtph264depay", "rtp-depay")
    h264parse = Gst.ElementFactory.make("h264parse", "h264-parser")
    nvv4l2decoder = Gst.ElementFactory.make("nvv4l2decoder", "nv-decoder")
    
    # Muxer
    nvstreammux = Gst.ElementFactory.make("nvstreammux", "nv-muxer")
    
    # Inference
    nvinfer = Gst.ElementFactory.make("nvinfer", "nv-inference")
    
    # Visualization & Sink
    nvvideoconvert = Gst.ElementFactory.make("nvvideoconvert", "nv-converter")
    nvdsosd = Gst.ElementFactory.make("nvdsosd", "nv-osd")
    
    # Sink (WSL2 preferred: nveglglessink, fallback: xvimagesink)
    sink = Gst.ElementFactory.make("nveglglessink", "nv-video-sink")
    if not sink:
        print("nveglglessink not found, falling back to xvimagesink")
        sink = Gst.ElementFactory.make("xvimagesink", "xv-sink")

    if not all([udpsrc, srtpdec, rtpdepay, h264parse, nvv4l2decoder, nvstreammux, nvinfer, nvvideoconvert, nvdsosd, sink]):
        sys.stderr.write(" One or more elements could not be created. Verify DeepStream and GStreamer plugins.\n")
        return

    # 5. Configure Elements
    # UDP Source
    udpsrc.set_property('port', SRTP_PORT)
    # Caps for the SRTP stream (Assumes H.264 payload 96)
    caps_udp = Gst.Caps.from_string("application/x-srtp,media=(string)video,clock-rate=(int)90000,encoding-name=(string)H264,payload=(int)96")
    udpsrc.set_property('caps', caps_udp)

    # Stream Muxer
    nvstreammux.set_property('width', 1920)
    nvstreammux.set_property('height', 1080)
    nvstreammux.set_property('batch-size', 1)
    nvstreammux.set_property('batched-push-timeout', 40000)
    
    # Inference
    nvinfer.set_property('config-file-path', YOLO_CONFIG_FILE)

    # 6. Add elements to pipeline
    pipeline.add(udpsrc)
    pipeline.add(srtpdec)
    pipeline.add(rtpdepay)
    pipeline.add(h264parse)
    pipeline.add(nvv4l2decoder)
    pipeline.add(nvstreammux)
    pipeline.add(nvinfer)
    pipeline.add(nvvideoconvert)
    pipeline.add(nvdsosd)
    pipeline.add(sink)

    # 7. Link Elements
    # udpsrc -> srtpdec -> rtpdepay -> h264parse -> nvv4l2decoder -> nvstreammux
    udpsrc.link(srtpdec)
    
    # Connect SRTP signal for key
    srtpdec.connect("request-key", srtp_request_key_callback)
    
    srtpdec.link(rtpdepay)
    rtpdepay.link(h264parse)
    h264parse.link(nvv4l2decoder)

    # Link decoder to stream muxer
    # nvstreammux requires requesting a sink pad
    sinkpad = nvstreammux.get_request_pad("sink_0")
    if not sinkpad:
        sys.stderr.write(" Unable to get the sink pad of nvstreammux \n")
        return
    
    srcpad = nvv4l2decoder.get_static_pad("src")
    if not srcpad:
        sys.stderr.write(" Unable to get source pad of decoder \n")
        return
    
    srcpad.link(sinkpad)

    # Continue linking: nvstreammux -> nvinfer -> nvvideoconvert -> nvdsosd -> sink
    nvstreammux.link(nvinfer)
    nvinfer.link(nvvideoconvert)
    nvvideoconvert.link(nvdsosd)
    nvdsosd.link(sink)

    # 8. Add Probe
    osd_sink_pad = nvdsosd.get_static_pad("sink")
    if osd_sink_pad:
        osd_sink_pad.add_probe(Gst.PadProbeType.BUFFER, osd_sink_pad_buffer_probe, 0)

    # 9. Start Pipeline
    loop = GLib.MainLoop()
    pipeline.set_state(Gst.State.PLAYING)
    print(f"DeepStream Pipeline Running...")
    print(f"Listening for SRTP H.264 stream on UDP port {SRTP_PORT}")
    print("Use netsh interface portproxy (on Windows) if streaming from external source to WSL2.")

    try:
        loop.run()
    except KeyboardInterrupt:
        print("Stopping...")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        pipeline.set_state(Gst.State.NULL)

if __name__ == '__main__':
    main()
