#!/usr/bin/env python3
import sys
import os
import gi
import time

gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

# Try to import pyds
try:
    import pyds
except ImportError:
    print("WARNING: 'pyds' library not found. DeepStream bindings are missing.")

# Constants
# RTMP URL: Replace this with your actual stream URL
# Example: "rtmp://192.168.1.100/live/drone" or "rtmp://localhost/live/stream"
RTMP_URL = "rtmp://localhost/live/stream" 

YOLO_CONFIG_FILE = "config_infer_primary_yolo.txt"

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
onnx-file=yolov8s.onnx
model-engine-file=yolov8s.onnx_b1_gpu0_fp32.engine
labelfile-path=labels.txt
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
parse-bbox-func-name=NvDsInferParseYolo
custom-lib-path=./libnvdsinfer_custom_impl_Yolo.so
engine-create-func-name=NvDsInferYoloCudaEngineGet

[class-attrs-all]
nms-iou-threshold=0.45
pre-cluster-threshold=0.25
topk=300
"""
    with open(YOLO_CONFIG_FILE, "w") as f:
        f.write(config_content)
    print(f"Generated {YOLO_CONFIG_FILE} with standard YOLO settings.")

def decodebin_pad_added_callback(element, pad, u_data):
    """
    Callback for decodebin 'pad-added' signal.
    """
    caps = pad.get_current_caps()
    if not caps:
        caps = pad.query_caps(None)
    
    structure = caps.get_structure(0)
    name = structure.get_name()
    
    print(f"DEBUG: Decodebin pad added: {pad.get_name()} with caps: {name}")

    if name.startswith("video"):
        # Link to the video converter (upload to GPU)
        # u_data is the sink pad of the converter
        converter_sink_pad = u_data
        if not converter_sink_pad.is_linked():
            print(f"SUCCESS: Linking decodebin video pad to converter")
            if pad.link(converter_sink_pad) == Gst.PadLinkReturn.OK:
                print("Video link successful")
            else:
                print("Video link failed")
        else:
            print("Converter sink pad already linked")
    elif name.startswith("audio"):
        # We can ignore audio or link to fakesink if needed, but decodebin handles unused pads gracefully usually.
        # For strictness, let's just print.
        print(f"Ignoring audio pad {pad.get_name()}")

def osd_sink_pad_buffer_probe(pad, info, u_data):
    """
    Probe to extract metadata and print detection info.
    """
    gst_buffer = info.get_buffer()
    if not gst_buffer:
        print("Unable to get GstBuffer")
        return Gst.PadProbeReturn.OK

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

    # 2. Generate Config (Ensure it exists)
    generate_yolo_config()

    # 3. Create Pipeline
    pipeline = Gst.Pipeline()
    if not pipeline:
        sys.stderr.write(" Unable to create Pipeline \n")
        return

    # 4. Create Elements
    # Source: RTMP -> Decodebin (Handles Demux & Decode)
    source = Gst.ElementFactory.make("rtmpsrc", "rtmp-source")
    decodebin = Gst.ElementFactory.make("decodebin", "decoder")
    
    # Bridge: System Memory -> NVMM (GPU Memory)
    # We need a converter to upload the raw decoded video to GPU memory
    mem_converter = Gst.ElementFactory.make("nvvideoconvert", "mem_converter")
    
    # CapsFilter to force NVMM memory
    caps = Gst.Caps.from_string("video/x-raw(memory:NVMM), format=NV12")
    caps_filter = Gst.ElementFactory.make("capsfilter", "caps_filter")
    caps_filter.set_property("caps", caps)
    
    # Muxer
    nvstreammux = Gst.ElementFactory.make("nvstreammux", "nv-muxer")
    
    # Inference
    nvinfer = Gst.ElementFactory.make("nvinfer", "nv-inference")
    
    # Visualization & Sink
    nvvideoconvert = Gst.ElementFactory.make("nvvideoconvert", "nv-converter")
    nvdsosd = Gst.ElementFactory.make("nvdsosd", "nv-osd")
    
    # Sink (WSL2 preferred: nveglglessink)
    sink = Gst.ElementFactory.make("nveglglessink", "nv-video-sink")
    if not sink:
        print("nveglglessink not found, falling back to xvimagesink")
        sink = Gst.ElementFactory.make("xvimagesink", "xv-sink")

    if not all([source, decodebin, mem_converter, caps_filter, nvstreammux, nvinfer, nvvideoconvert, nvdsosd, sink]):
        sys.stderr.write(" One or more elements could not be created. Verify GStreamer plugins.\n")
        return

    # 5. Configure Elements
    # RTMP Source
    source.set_property('location', RTMP_URL)
    # Important: decodebin handles buffering, but do-timestamp helps
    source.set_property('do-timestamp', True)
    
    # Stream Muxer
    nvstreammux.set_property('width', 1920)
    nvstreammux.set_property('height', 1080)
    nvstreammux.set_property('batch-size', 1)
    nvstreammux.set_property('batched-push-timeout', 40000)
    nvstreammux.set_property('live-source', 1)
    
    # Inference
    nvinfer.set_property('config-file-path', YOLO_CONFIG_FILE)

    # Sink Sync Strategy
    sink.set_property('sync', False)

    # 6. Add elements to pipeline
    pipeline.add(source)
    pipeline.add(decodebin)
    pipeline.add(mem_converter)
    pipeline.add(caps_filter)
    pipeline.add(nvstreammux)
    pipeline.add(nvinfer)
    pipeline.add(nvvideoconvert)
    pipeline.add(nvdsosd)
    pipeline.add(sink)

    # 7. Link Elements
    # rtmpsrc -> decodebin
    source.link(decodebin)
    
    # decodebin is dynamic. We link it to mem_converter in the callback.
    converter_sink_pad = mem_converter.get_static_pad("sink")
    decodebin.connect("pad-added", decodebin_pad_added_callback, converter_sink_pad)
    
    # mem_converter -> caps_filter -> nvstreammux
    mem_converter.link(caps_filter)
    
    # Link caps_filter -> nvstreammux (request pad)
    sinkpad = nvstreammux.get_request_pad("sink_0")
    srcpad = caps_filter.get_static_pad("src")
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

    # Add Bus Watch for Error Handling
    def bus_call(bus, message, loop):
        t = message.type
        if t == Gst.MessageType.EOS:
            sys.stdout.write("End-of-stream\n")
            loop.quit()
        elif t == Gst.MessageType.WARNING:
            err, debug = message.parse_warning()
            sys.stderr.write("Warning: %s: %s\n" % (err, debug))
        elif t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            sys.stderr.write("Error: %s: %s\n" % (err, debug))
            loop.quit()
        return True

    # 9. Start Pipeline
    loop = GLib.MainLoop()
    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect("message", bus_call, loop)
    
    pipeline.set_state(Gst.State.PLAYING)
    print(f"DeepStream Pipeline Running...")
    print(f"Connecting to RTMP Stream: {RTMP_URL}")
    print("Ensure the stream is active before or shortly after starting.")

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