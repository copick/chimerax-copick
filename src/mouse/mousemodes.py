# vim: set expandtab shiftwidth=4 softtabstop=4:

from chimerax.mouse_modes.mousemodes import MouseMode


class WheelMovePlanesMode(MouseMode):
    name = "move copick planes"
    # icon_file = './icons/delete.png'

    def __init__(self, session):
        MouseMode.__init__(self, session)

    def wheel(self, event):
        """
        Supported API.
        Override this method to handle mouse wheel events.
        """
        # print(event.wheel_value())
        # Sanity checks
        if not hasattr(self.session, "copick"):
            return
        if not hasattr(self.session, "ArtiaX"):
            return

        cpk = self.session.copick
        if cpk.active_volume is None or cpk.active_volume.deleted:
            return

        # Do the moving
        vol = cpk.active_volume
        vmin = vol.min_offset
        vmax = vol.max_offset

        if event.wheel_value() != 0:
            new_pos = vol.slab_position + event.wheel_value() * vol.pixelsize[0]
            new_pos = min(max(new_pos, vmin), vmax)
            vol.slab_position = new_pos


class _CopickPlaneMode(MouseMode):
    """Base for modes that act on the point where the mouse ray meets the shown tomogram plane (single plane,
    orthoplanes or tilted slab)."""

    def _tool(self):
        return getattr(self.session, "copick", None)

    def _ray(self, event):
        x, y = event.position()
        return self.session.main_view.clip_plane_points(x, y)

    def _plane_point(self, event):
        from chimerax.markers.mouse import volume_plane_intercept

        tool = self._tool()
        if tool is None or tool.active_volume is None or tool.active_volume.deleted:
            return None
        xyz1, xyz2 = self._ray(event)
        if xyz1 is None:
            return None
        xyz, _v = volume_plane_intercept(xyz1, xyz2, [tool.active_volume])
        if xyz is None:
            self.session.logger.status("copick: click on the shown tomogram plane (slab, orthoplanes or tilted slab)")
        return xyz

    def _pixel_tolerance(self, xyz, pixels: float = 8.0) -> float:
        return self.session.main_view.pixel_size(xyz) * pixels


class TraceFilamentMode(_CopickPlaneMode):
    """Click on the tomogram plane to add a control point to the active filament; drag a control point to move it;
    shift-click a control point to remove it."""

    name = "trace copick filament"

    def __init__(self, session):
        _CopickPlaneMode.__init__(self, session)
        self._drag = None

    def _controller(self):
        tool = self._tool()
        return getattr(tool, "filaments", None) if tool is not None else None

    def enable(self):
        ctl = self._controller()
        if ctl is not None:
            ctl.mode_enabled(self.name)

    def mouse_down(self, event):
        MouseMode.mouse_down(self, event)
        ctl = self._controller()
        if ctl is None or ctl.active is None:
            self.session.logger.status("copick: open or create a filament set first")
            return
        xyz1, xyz2 = self._ray(event)
        if xyz1 is not None:
            p = self._plane_point(event)
            tol = self._pixel_tolerance(p if p is not None else xyz1)
            hit = ctl.hit_control(xyz1, xyz2, tol)
            if hit is not None:
                if event.shift_down():
                    ctl.remove_point(*hit)
                else:
                    ctl.set_active_filament(hit[0])
                    ctl.begin_drag()
                    self._drag = hit
                return
        p = self._plane_point(event)
        if p is not None:
            ctl.add_point(p)

    def mouse_drag(self, event):
        if self._drag is None:
            return
        p = self._plane_point(event)
        if p is not None:
            self._controller().move_point(self._drag[0], self._drag[1], p)

    def mouse_up(self, event):
        if self._drag is not None:
            ctl = self._controller()
            if ctl is not None:
                ctl.end_drag()
        self._drag = None
        MouseMode.mouse_up(self, event)


class CutFilamentMode(TraceFilamentMode):
    """Click on a filament (on the tomogram plane) to cut it in two there."""

    name = "cut copick filament"

    def mouse_down(self, event):
        MouseMode.mouse_down(self, event)
        ctl = self._controller()
        if ctl is None or ctl.active is None:
            self.session.logger.status("copick: open or create a filament set first")
            return
        p = self._plane_point(event)
        if p is not None:
            ctl.cut_at(p)

    def mouse_drag(self, event):
        pass

    def mouse_up(self, event):
        MouseMode.mouse_up(self, event)


class PaintInstanceMode(_CopickPlaneMode):
    """Paint the current instance ID (a sphere of the brush radius) where the mouse meets the tomogram plane."""

    name = "paint copick instance"
    value = None  # None = the current ID

    def _controller(self):
        tool = self._tool()
        return getattr(tool, "segmentations", None) if tool is not None else None

    def _apply(self, event):
        ctl = self._controller()
        if ctl is None or not ctl.editing:
            self.session.logger.status("copick: start editing an instance segmentation first")
            return
        p = self._plane_point(event)
        if p is not None:
            ctl.paint(p, value=self.value)

    def mouse_down(self, event):
        MouseMode.mouse_down(self, event)
        self._apply(event)

    def mouse_drag(self, event):
        self._apply(event)

    def mouse_up(self, event):
        ctl = self._controller()
        if ctl is not None:
            ctl.flush()
        MouseMode.mouse_up(self, event)


class EraseInstanceMode(PaintInstanceMode):
    """Erase instance voxels (set them to background)."""

    name = "erase copick instance"
    value = 0


class PickInstanceMode(_CopickPlaneMode):
    """Make the instance ID under the mouse (on the tomogram plane) the current ID."""

    name = "pick copick instance"

    def mouse_down(self, event):
        MouseMode.mouse_down(self, event)
        tool = self._tool()
        ctl = getattr(tool, "segmentations", None) if tool is not None else None
        if ctl is None or not ctl.editing:
            return
        p = self._plane_point(event)
        if p is not None:
            ctl.pick(p)


COPICK_EDIT_MODES = (TraceFilamentMode, CutFilamentMode, PaintInstanceMode, EraseInstanceMode, PickInstanceMode)
