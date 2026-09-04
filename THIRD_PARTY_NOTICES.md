# Third-party notices

Release packages include an unmodified FFmpeg executable for video conversion.
FFmpeg is a separate program and is licensed under the GNU GPL version 3 in the
configuration distributed by the release workflow. Copyright and source/license
information are available from [ffmpeg.org](https://ffmpeg.org/).

VTrack Shot Tracker invokes FFmpeg as a command-line process and does not link
against FFmpeg libraries.

Release packages also include pywebview (BSD-3-Clause), pythonnet (MIT),
clr-loader, Bottle (MIT), proxy_tools (MIT), CFFI (MIT-0), pycparser
(BSD-3-Clause), and typing_extensions (PSF-2.0) to host the local interface in
a native Windows WebView2 window. Their copyright and license texts are
distributed in their package metadata and source repositories.

Microsoft Edge WebView2 Runtime is a separately installed Microsoft component;
it is detected and used but is not redistributed by this project.
