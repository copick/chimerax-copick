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
