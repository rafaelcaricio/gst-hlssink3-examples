import sys
import traceback
import itertools
import logging
from typing import Optional

import gi
gi.require_version('Gst', '1.0')
from gi.repository import GObject, Gst

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger('hls_server')


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


class FileHlsOrigin:
    def __init__(self, filename: str) -> None:
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
        # videoscale = gst_element("videoscale")
        video_encoder = gst_element("vtenc_h264_hw")
        h264parse = gst_element("h264parse")

        audio_queue = gst_element("queue")

        hlssink3 = gst_element("hlssink3", "hls")
        hlssink3.set_property("playlist-location", "master.m3u8")
        hlssink3.set_property("target-duration", 6)
        hlssink3.set_property("playlist-length", 5)
        hlssink3.set_property("max-files", 5)

        self.pipeline.add(self.origin)
        self.pipeline.add(self.videoconvert)
        self.pipeline.add(self.audioconvert)
        self.pipeline.add(audio_encoder)
        self.pipeline.add(video_queue)
        # self.pipeline.add(videoscale)
        self.pipeline.add(video_encoder)
        self.pipeline.add(h264parse)
        self.pipeline.add(audio_queue)
        self.pipeline.add(hlssink3)

        self.pipeline.link(self.origin)
        Gst.Element.link_many(self.videoconvert, video_queue, video_encoder, h264parse, hlssink3)
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
            log.info(f"Audio pad added to origin element: {new_pad_type}")
            audioconvert_sink = self.audioconvert.get_static_pad('sink')
            if audioconvert_sink.is_linked():
                log.warning("Already linked audio contents source. Ignoring..")
            new_pad.link(audioconvert_sink)

        elif new_pad_type.startswith('video/'):
            log.info(f"Video pad added to origin element: {new_pad_type}")
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

    loop = GObject.MainLoop()
    bus = origin.pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect("message", bus_call, loop)

    # start play back and listed to events
    origin.pipeline.set_state(Gst.State.PLAYING)
    try:
        print("Running pipeline..")
        loop.run()
    finally:
        # cleanup
        origin.pipeline.set_state(Gst.State.NULL)
        print("All good! ;)")


def fail(message: str) -> None:
    traceback.print_stack()
    print(f"\nFailure: {message}")
    sys.exit(1)


def pairwise(iterable):
    a, b = itertools.tee(iterable)
    next(b, None)
    return zip(a, b)


def link_many(*args):
    for pair in pairwise(args):
        if not pair[0].link(pair[1]):
            fail(f'Failed to link {pair[0]} and {pair[1]}')


if __name__ == '__main__':
    main()