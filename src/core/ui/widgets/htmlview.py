# vim: set expandtab shiftwidth=4 softtabstop=4:

"""
HtmlView is a derived class from PyQt5.QtWebEngineWidgets.QWebEngineView
that simplifies using custom schemes and intercepting navigation requests.

HtmlView may be instantiated just like QWebEngineView, but handles
three extra keyword arguments:

    size_hint:   a QSize compatible value, typically (width, height),
                 specifying the preferred initial size for the view.
    interceptor: a callback function taking one argument, an instance
                 of QWebEngineUrlRequestInfo, invoked to handle navigation
                 requests.
    schemes:     an iterable of custom schemes that will be used in the
                 view.  If schemes is specified, then interceptor will
                 be called when custom URLs are clicked.
    download:    a callback function taking one argument, an instance
                 of QWebEngineDownloadItem, invoked when download is
                 requested.
"""

from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
from PyQt5.QtWebEngineCore import QWebEngineUrlRequestInterceptor
from PyQt5.QtWebEngineCore import QWebEngineUrlSchemeHandler


class HtmlView(QWebEngineView):

    def __init__(self, *args, size_hint=None, schemes=None,
                 interceptor=None, download=None, **kw):
        super().__init__(*args, **kw)
        self._size_hint = size_hint
        if interceptor is None:
            self._intercept = None
        else:
            self._intercept = _RequestInterceptor(callback=interceptor)
        self._download = download
        if schemes is None:
            self._schemes = []
        else:
            self._schemes = [s.encode("utf-8") for s in schemes]
            self._scheme_handler = _SchemeHandler()
        self._known_profiles = set()

    def sizeHint(self):
        if self._size_hint:
            from PyQt5.QtCore import QSize
            return QSize(*self._size_hint)
        else:
            return super().sizeHint()

    def setHtml(self, html):
        self.setEnabled(False)
        if len(html) < 1000000:
            super().setHtml(html)
        else:
            try:
                tf = open(self._tf_name, "wb")
            except AttributeError:
                import tempfile, atexit
                tf = tempfile.NamedTemporaryFile(prefix="chbp", suffix=".html",
                                                 delete=False, mode="wb")
                self._tf_name = tf.name
                def clean(filename):
                    import os
                    try:
                        os.remove(filename)
                    except OSError:
                        pass
                atexit.register(clean, tf.name)
            from PyQt5.QtCore import QUrl
            tf.write(bytes(html, "utf-8"))
            # On Windows, we have to close the temp file before
            # trying to open it again (like loading HTML from it).
            tf.close()
            self.load(QUrl.fromLocalFile(self._tf_name))
        self.setEnabled(True)
        self._update_profile()

    def setUrl(self, url):
        super().setUrl(url)
        self._update_profile()

    def _update_profile(self):
        p = self.page().profile()
        if p not in self._known_profiles:
            if self._intercept:
                p.setRequestInterceptor(self._intercept)
                for scheme in self._schemes:
                    p.installUrlSchemeHandler(scheme, self._scheme_handler)
            if self._download:
                p.downloadRequested.connect(self._download)
            self._known_profiles.add(p)


class _RequestInterceptor(QWebEngineUrlRequestInterceptor):

    def __init__(self, *args, callback=None, **kw):
        super().__init__(*args, **kw)
        self._callback = callback

    def interceptRequest(self, info):
        # "info" is an instance of QWebEngineUrlRequestInfo
        if self._callback:
            self._callback(info)


class _SchemeHandler(QWebEngineUrlSchemeHandler):
    def requestStarted(self, request):
        # "request" is an instance of QWebEngineUrlRequestJob
        # We do nothing because caller should be intercepting
        # custom URL navigation already
        pass