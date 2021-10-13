import math
import sys
import traceback
import logging
from enum import Enum
from typing import Optional

import gi
gi.require_version('Gst', '1.0')
from gi.repository import GLib, Gst

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger('hls_server')


class FileHlsOrigin:
    def __init__(
            self,
            filename: str,
            target_duration_secs: int = 6,
            fps: float = 29.97,
    ) -> None:
        if Gst.uri_is_valid(filename):
            self.uri = filename
        else:
            self.uri = Gst.filename_to_uri(filename)

        self.pipeline = Gst.Pipeline.new("FileHlsOrigin")

        self.origin = gst_element("uridecodebin", "origin")
        self.origin.set_property('uri', self.uri)
        self.origin.connect("pad-added", self.on_origin_pad_added)

        self.videoconvert = gst_element("videoconvert")
        self.audioconvert = gst_element("audioconvert")
        audio_encoder = gst_element("avenc_aac")

        video_queue = gst_element("queue")
        videoscale = gst_element("videoscale")

        videoscale_capsfilter = gst_element("capsfilter")
        videoscale_capsfilter.props.caps = Gst.caps_from_string("video/x-raw,format=I420,width=960,height=540")

        video_encoder = gst_element("x264enc")
        video_encoder.set_property("bitrate", 2100)

        key_int_max = math.ceil(fps) * target_duration_secs
        video_encoder.set_property("key-int-max", key_int_max)
        log.debug(f"x264enc.key-int-max={key_int_max}")

        video_encoder.set_property("speed-preset", "fast")
        video_encoder.set_property("option-string", "scenecut=0")
        video_encoder.set_property("tune", "zerolatency")

        video_encoder_capsfilter = gst_element("capsfilter")
        video_encoder_capsfilter.props.caps = Gst.caps_from_string(
            f"video/x-h264,stream-format=avc,alignment=au,profile=main")

        h264parse = gst_element("h264parse")

        audio_queue = gst_element("queue")

        hlssink3 = gst_element("hlssink3", "hls")
        hlssink3.set_property("location", "segment%05d.ts")
        hlssink3.set_property("playlist-location", "master.m3u8")
        hlssink3.set_property("target-duration", target_duration_secs)
        hlssink3.set_property("playlist-length", 15)
        hlssink3.set_property("max-files", 16)

        self.pipeline.add(self.origin)
        self.pipeline.add(self.videoconvert)
        self.pipeline.add(self.audioconvert)
        self.pipeline.add(audio_encoder)
        self.pipeline.add(video_queue)
        self.pipeline.add(videoscale)
        self.pipeline.add(videoscale_capsfilter)
        self.pipeline.add(video_encoder)
        self.pipeline.add(video_encoder_capsfilter)
        self.pipeline.add(h264parse)
        self.pipeline.add(audio_queue)
        self.pipeline.add(hlssink3)

        self.pipeline.link(self.origin)
        Gst.Element.link_many(
            self.videoconvert, video_queue, videoscale, videoscale_capsfilter, video_encoder,
            video_encoder_capsfilter, h264parse, hlssink3
        )
        Gst.Element.link_many(self.audioconvert, audio_queue, audio_encoder)

        hls_sink_pad_templ = hlssink3.get_pad_template('audio')
        hls_sink = hlssink3.request_pad(hls_sink_pad_templ)

        audio_encoder_src = audio_encoder.get_static_pad('src')

        audio_encoder_src.link(hls_sink)

    def on_origin_pad_added(self, _src, new_pad):
        new_pad_caps = new_pad.get_current_caps()
        new_pad_struct = new_pad_caps.get_structure(0)
        new_pad_type = new_pad_struct.get_name()

        if new_pad_type.startswith("audio/"):
            log.debug(f"Audio pad added to origin element: {new_pad_type}")
            audioconvert_sink = self.audioconvert.get_static_pad('sink')
            if audioconvert_sink.is_linked():
                log.warning("Already linked audio contents source. Ignoring..")
            new_pad.link(audioconvert_sink)

        elif new_pad_type.startswith('video/'):
            log.debug(f"Video pad added to origin element: {new_pad_type}")
            videoconvert_sink = self.videoconvert.get_static_pad('sink')
            if videoconvert_sink.is_linked():
                log.warning("Already linked video contents source. Ignoring..")
                return
            new_pad.link(videoconvert_sink)

        else:
            log.error(f"New unexpected pad added to origin element with type: {new_pad_type}")


def main():
    Gst.init(None)

    if len(sys.argv) <= 1:
        fail("Needs at least one argument")

    origin = FileHlsOrigin(sys.argv[-1])

    loop = GLib.MainLoop()
    bus = origin.pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect("message", bus_call, loop)

    # start play back and listed to events
    origin.pipeline.set_state(Gst.State.PLAYING)
    try:
        print("Running pipeline..")
        loop.run()
    except KeyboardInterrupt:
        log.info("Stopping pipeline...")
    finally:
        # cleanup
        origin.pipeline.set_state(Gst.State.NULL)
        log.info("All good! ;)")


def bus_call(_bus, message, loop):
    t = message.type
    if t == Gst.MessageType.EOS:
        print("End-of-stream")
        loop.quit()
    elif t == Gst.MessageType.ERROR:
        err, debug = message.parse_error()
        fail(f"Bus error: {err}:{debug}")
        loop.quit()
    return True


def gst_element(element_name: str, alias: Optional[str] = None) -> Gst.Element:
    element = Gst.ElementFactory.make(element_name, alias)
    if element is None:
        fail(f"Could not find element {element_name}")
    return element


def fail(message: str) -> None:
    traceback.print_stack()
    log.error(f"\nFailure: {message}")
    sys.exit(1)


if __name__ == '__main__':
    main()
