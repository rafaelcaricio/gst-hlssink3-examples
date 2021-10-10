# GStreamer HTTP Live Streaming Examples

This repository contains some examples of usage of the GStreamer HLS plugin `hlssink3`.

## Available Examples

### Serving a video file to live HLS

The example `hlssink3_server.py` reads from a local file and generates a HLS manifest and segment files. The files are
updated in realtime for live streaming.

## Installation

Needs Python 3.9 (as of today 2021-10-10).

Make sure GStreamer is installed and available:
```
$ pkg-config --print-errors --exists gstreamer-1.0
```

If GStreamer dependency is not installed, please try the those
[installation steps](https://gitlab.freedesktop.org/gstreamer/gstreamer-rs/-/blob/068b078edfa4f2f10e1824b41548c965b710626d/gstreamer/README.md#installation).

#### MacOS Specific
Make sure `pkg-config` version being used can find all libs installed using `brew`:
```
$ export PKG_CONFIG_PATH="/usr/local/lib/pkgconfig"
```

#### Building Python Bindings
In order to be able to use the GStreamer bindings in a virtualenv. We need to build from source.
Checkout the code from https://gitlab.freedesktop.org/gstreamer/gst-python/-/tree/master
```
$ meson builddir
$ cd builddir
$ ninja -v
$ ninja install -v
```

The `ninja install` will attempt to install, but we need to manually copy the overrides, if we want to use under a virtualenv.
```
$ cp gi/overrides/_gi_gst.cpython-39-darwin.so ~/.pyenv/versions/gstreamer/lib/python3.9/site-packages/gi/overrides
$ cp ~/development/opensource/gst-python/gi/overrides/GstPbutils.py ~/.pyenv/versions/gstreamer/lib/python3.9/site-packages/gi/overrides
$ cp ~/development/opensource/gst-python/gi/overrides/Gst.py ~/.pyenv/versions/gstreamer/lib/python3.9/site-packages/gi/overrides
```

### Additional Info

Example of sometimes pad: https://github.com/gkralik/python-gst-tutorial/blob/master/basic-tutorial-3.py
