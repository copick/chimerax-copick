from qtpy.QtGui import QSurface, QWindow


class OrthoViewCanvas(QWindow):
    def __init__(self, parent, view, session, panel):
        QWindow.__init__(self)
        from Qt.QtWidgets import QWidget

        self.widget = QWidget.createWindowContainer(self, parent)
        self.setSurfaceType(QSurface.SurfaceType.OpenGLSurface)
        self.view = view
        self.session = session
        self.panel = panel
        self.main_view = session.main_view

        self.handler = session.triggers.add_handler("frame drawn", self._redraw)
        from Qt.QtCore import QSize

        self.widget.setMinimumSize(QSize(20, 20))

    def close(self):
        self.session.triggers.remove_handler(self.handler)
        self.setParent(None)
        QWindow.destroy(self)

    def _redraw(self, *_):
        self.render()

    def exposeEvent(self, event):  # noqa
        if self.isExposed() and not self.session.update_loop.blocked():
            self.render()

    def resizeEvent(self, event):  # noqa
        size = event.size()
        width = size.width()
        height = size.height()
        self.set_viewport(width, height)

    def set_viewport(self, width, height):
        # Don't need make_current, since OpenGL isn't used
        # until rendering
        self.view.resize(width, height)

    def render(self):
        ww, wh = self.main_view.window_size
        if ww <= 0 or wh <= 0:
            return
        width, height = self.view.window_size
        if width <= 0 or height <= 0:
            return
        # temporary workaround for #2162
        if self.view is None or self.view.render is None:
            return

        # self.view.set_background_color((.3, .3, .3, 1))  # DEBUG
        mvwin = self.view.render.use_shared_context(self)
        try:
            self.view.draw()
            # if has_string_marker:
            #     text = b"End SideView"
            #     string_marker.glStringMarkerGREMEDY(len(text), text)
        finally:
            # Target opengl context back to main graphics window.
            self.main_view.render.use_shared_context(mvwin)
        self.view.render.done_current()

    def mousePressEvent(self, event):  # noqa
        pass

    def mouseReleaseEvent(self, event):  # noqa
        pass

    def mouseMoveEvent(self, event):  # noqa
        pass

    def keyPressEvent(self, event):  # noqa
        return self.session.ui.forward_keystroke(event)
