"""Spotlight mode: show only a (gaussian-weighted) sphere of tomogram data around the active particle.

The spotlight is a small derived Volume built from the displayed tomogram's data around the
active particle. Data outside the sphere is blended toward the whole-volume mean ("fill"), so
the field is constant outside the sphere and rendering fades out radially. Data keeps its raw
polarity; for the usual dark-features-on-bright-background tomograms the isosurface threshold
sits below the mean (box faces are disabled so the enclosing background produces no caps), the
volume/MIP opacity ramp descends with value, and MIP works because ChimeraX maxes the
colormapped plane colors (GL_MAX blending), not the raw data. All levels are in raw tomogram
units, matching what the ChimeraX volume viewer shows.
"""

import time
from functools import partial
from typing import List, Optional, Tuple

import numpy as np
from chimerax.core.commands import run
from superqt.utils import thread_worker

MODES = ("surface", "mesh", "volume", "mip")
FEATURES = ("dark", "light")


def _background_luminance(session) -> float:
    r, g, b = session.main_view.background_color[:3]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _feature_rgba(session) -> Tuple[float, float, float, float]:
    """Feature render color: inverse of the view background."""
    if _background_luminance(session) >= 0.5:
        return (0.15, 0.15, 0.15, 1.0)
    return (1.0, 1.0, 1.0, 1.0)


class LevelEstimator:
    """Estimate render levels from whole-volume statistics (raw tomogram units).

    Always uses full-volume statistics so the contrast does not change with the
    spotlight position. For dark-feature data thresholds land below the mean.
    """

    def __init__(self, vol):
        ms = vol.matrix_value_statistics()
        if hasattr(vol, "mean") and hasattr(vol, "std"):
            # ArtiaX VolumePlus computes these over the full displayed array at load.
            self.mean = float(vol.mean)
            self.std = float(vol.std)
            self.median = float(vol.median)
            self.min = float(vol.min)
            self.max = float(vol.max)
        else:
            mean, sd, _ = vol.mean_sd_rms()
            self.mean, self.std = float(mean), float(sd)
            self.median = float(ms.rank_data_value(0.5))
            self.min, self.max = float(ms.minimum), float(ms.maximum)
        self.p01 = float(ms.rank_data_value(0.01))
        self.p99 = float(ms.rank_data_value(0.99))

    def surface_level(self, features: str) -> float:
        # Below the mean for dark features (above for light); mean +/- 2*std is less
        # outlier-dominated than an extreme percentile (fiducials, ice contamination).
        if features == "dark":
            return max(self.mean - 2.0 * self.std, self.min)
        return min(self.mean + 2.0 * self.std, self.max)

    # Peak brightness of the volume-rendering ramp. Kept below 1.0: at full
    # saturation the features clip to flat white and interior gradation is lost.
    MAX_BRIGHTNESS = 0.9

    def image_levels(self, features: str) -> List[Tuple[float, float]]:
        # Opacity ramp over the [mean - 3*std, mean + 0.5*std] window (mirrored for
        # light features), near-full opacity at the strong-feature end. For dark
        # features the brightness descends with value.
        b = self.MAX_BRIGHTNESS
        if features == "dark":
            lo = max(self.mean - 3.0 * self.std, self.min)
            hi = min(self.mean + 0.5 * self.std, self.max)
            return [(lo, b), (hi, 0.0)]
        lo = max(self.mean - 0.5 * self.std, self.min)
        hi = min(self.mean + 3.0 * self.std, self.max)
        return [(lo, 0.0), (hi, b)]


def _compute_spotlight_impl(vol, region, center_ijk, voxel_size, radius, weighted, fill):
    """Read the region and blend it toward fill with a spherical (gaussian) weight.

    Runs in a background thread; must only read from vol. Distances are computed in
    grid-index space scaled by the voxel size, which is exact for rigid rotations.
    """
    t0 = time.perf_counter()
    m = vol.region_matrix(region)
    if m is None:
        return None
    m = m.astype(np.float32, copy=True)

    ijk_min, _, ijk_step = region
    nz, ny, nx = m.shape
    d = []
    for axis, n in ((0, nx), (1, ny), (2, nz)):
        idx = ijk_min[axis] + ijk_step[axis] * np.arange(n, dtype=np.float32)
        d.append((idx - center_ijk[axis]) * voxel_size[axis])
    dx, dy, dz = d
    r2 = (
        (dx * dx).reshape(1, 1, nx)
        + (dy * dy).reshape(1, ny, 1)
        + (dz * dz).reshape(nz, 1, 1)
    )

    rad2 = radius * radius
    if weighted:
        sigma = radius / 3.0
        w = np.exp(r2 * np.float32(-0.5 / (sigma * sigma)))
        w[r2 > rad2] = np.float32(0.0)
    else:
        w = (r2 <= rad2).astype(np.float32)

    fill = np.float32(fill)
    out = fill + w * (m - fill)

    origin = tuple(float(x) for x in vol.data.ijk_to_xyz(ijk_min))
    step = tuple(s * v for s, v in zip(ijk_step, voxel_size))
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    return out.astype(np.float32, copy=False), origin, step, elapsed_ms


_compute_spotlight = thread_worker(_compute_spotlight_impl)


class SpotlightManager:
    """Owns the spotlight state, the derived Volume and all trigger wiring."""

    def __init__(self, tool):
        self.tool = tool
        self.session = tool.session

        # Config (radius/weighted/mode/features/particles persist via CoPickSettings).
        s = tool.settings
        self.radius = float(getattr(s, "spotlight_radius", 500.0))
        self.weighted = bool(getattr(s, "spotlight_weighted", True))
        self.mode = str(getattr(s, "spotlight_mode", "volume"))
        self.features = str(getattr(s, "spotlight_features", "dark"))
        self.hide_particles = bool(getattr(s, "spotlight_particles", False))
        if self.mode not in MODES:
            self.mode = "volume"
        if self.features not in FEATURES:
            self.features = "dark"
        # Level overrides in raw tomogram units; None = auto-estimated (session-only).
        self.surface_level: Optional[float] = None
        self.image_levels: Optional[List[Tuple[float, float]]] = None

        # Runtime state
        self.enabled = False
        self.debug = True
        self._threaded = True  # flip to False for synchronous debugging
        self._inplace = True  # flip to False to rebuild the volume on every update
        self._custom_color = None  # user-picked color adopted from the volume viewer
        self._updating_style = False  # guards against adopting our own changes
        self._grid = None
        self._vol = None
        self._center: Optional[Tuple[float, float, float]] = None
        self._fill: Optional[float] = None
        self._estimator: Optional[LevelEstimator] = None
        self._saved_source_display: Optional[bool] = None
        self._sel_handler = None
        self._worker_active = False
        self._pending_center: Optional[Tuple[float, float, float]] = None
        self._seq = 0
        self._warned_level = False

    # ------------------------------------------------------------------ lifecycle

    def enable(self):
        if self.enabled:
            self._dbg("already enabled")
            return

        vol = self._source_volume()
        if vol is None:
            self.session.logger.warning(
                "Spotlight: no tomogram loaded. Use 'copick open run' first."
            )
            return

        if tuple(getattr(vol.data, "cell_angles", (90, 90, 90))) != (90, 90, 90):
            self.session.logger.warning(
                "Spotlight: non-orthogonal cell angles; sphere distances may be inaccurate."
            )

        self._fill = (
            float(vol.mean) if hasattr(vol, "mean") else float(vol.mean_sd_rms()[0])
        )
        self._estimator = LevelEstimator(vol)
        self._warned_level = False

        self._saved_source_display = bool(vol.display)
        vol.display = False
        if not self.hide_particles:
            # By default all particles stay visible in spotlight mode.
            self._particles_show_all()

        from chimerax.core.selection import SELECTION_CHANGED

        self._sel_handler = self.session.triggers.add_handler(
            SELECTION_CHANGED, self._on_selection
        )

        self.enabled = True
        self._dbg(
            f"enabled r={self.radius:g} weighted={self.weighted} mode={self.mode} "
            f"features={self.features} fill={self._fill:.4g}"
        )

        # Switch to the select mouse mode so the user can right-click particles.
        run(self.session, "ui mousemode right select", log=False)

        center = self._active_particle_position()
        if center is not None:
            self.on_active_particle(center)
        self.session.logger.status(
            "Spotlight on — right-click a particle to move the spotlight (or step with aa/dd)",
            log=(center is None),
        )

    def disable(self, restore_volume: bool = True):
        if not self.enabled:
            return
        self.enabled = False
        self._pending_center = None

        if self._sel_handler is not None:
            self._sel_handler.remove()
            self._sel_handler = None

        if self._vol is not None and not self._vol.deleted:
            try:
                self._vol.remove_volume_change_callback(self._on_volume_changed)
            except ValueError:
                pass
            self._vol.delete()
        self._vol = None
        self._grid = None
        self._center = None
        self._estimator = None

        if restore_volume:
            vol = self._source_volume()
            if vol is not None:
                vol.display = (
                    self._saved_source_display
                    if self._saved_source_display is not None
                    else True
                )
        self._saved_source_display = None

        # Leave all particles visible when exiting spotlight; the next stepper action
        # re-applies its own only-active mask.
        self._particles_show_all()
        self._dbg("disabled")

    def toggle(self):
        if self.enabled:
            self.disable()
        else:
            self.enable()

    def shutdown(self):
        """Cleanup on tool teardown."""
        try:
            self.disable(restore_volume=True)
        except Exception:
            pass
        if self._sel_handler is not None:
            try:
                self._sel_handler.remove()
            except Exception:
                pass
            self._sel_handler = None

    # ---------------------------------------------------------------- configuration

    def configure(
        self,
        radius=None,
        weighted=None,
        mode=None,
        features=None,
        surface_level=None,
        image_levels=None,
        particles=None,
    ):
        s = self.tool.settings
        recompute = False
        restyle = False

        if radius is not None:
            if radius <= 0:
                self.session.logger.warning("Spotlight: radius must be positive.")
            elif float(radius) != self.radius:
                self.radius = float(radius)
                s.spotlight_radius = self.radius
                recompute = True

        if weighted is not None and bool(weighted) != self.weighted:
            self.weighted = bool(weighted)
            s.spotlight_weighted = self.weighted
            recompute = True

        if features is not None and features != self.features:
            self.features = features
            s.spotlight_features = features
            self._warned_level = False
            self._custom_color = None
            restyle = True

        if mode is not None and mode != self.mode:
            self.mode = mode
            s.spotlight_mode = mode
            restyle = True

        if surface_level is not None:
            self.surface_level = float(surface_level)
            self._warned_level = False
            restyle = True

        if image_levels is not None:
            self.image_levels = list(image_levels)
            restyle = True

        if particles is not None and bool(particles) != self.hide_particles:
            self.hide_particles = bool(particles)
            s.spotlight_particles = self.hide_particles
            if self.enabled:
                if self.hide_particles and self._center is not None:
                    self._update_particle_masks(self._center)
                elif not self.hide_particles:
                    self._particles_show_all()

        if self.enabled:
            if restyle:
                self._apply_render_mode()
            if recompute and self._center is not None:
                self._request_update(self._center)

    def status(self) -> str:
        return (
            f"Spotlight {'ON' if self.enabled else 'off'} — radius {self.radius:g} Å, "
            f"{'gaussian' if self.weighted else 'hard'} edge, mode {self.mode}, "
            f"features {self.features}, particles "
            f"{'hidden outside sphere' if self.hide_particles else 'unaffected'}. "
            f"Use 'copick spotlight report' for level details."
        )

    def report(self):
        """Log whole-volume stats and the auto-estimated (or overridden) levels."""
        vol = self._source_volume()
        if vol is None:
            self.session.logger.warning(
                "Spotlight: no tomogram loaded. Use 'copick open run' first."
            )
            return
        est = self._estimator if (self.enabled and self._estimator) else LevelEstimator(vol)
        bg_light = _background_luminance(self.session) >= 0.5
        log = self.session.logger.info

        log(
            f"[spotlight] whole-volume stats: mean={est.mean:.4g} std={est.std:.4g} "
            f"median={est.median:.4g} p1={est.p01:.4g} p99={est.p99:.4g} "
            f"min={est.min:.4g} max={est.max:.4g}"
        )
        log(
            f"[spotlight] features={self.features}, background="
            f"{'light' if bg_light else 'dark'} -> features render "
            f"{'dark' if bg_light else 'white'}"
        )

        sl = self.surface_level if self.surface_level is not None else est.surface_level(self.features)
        src_s = "user" if self.surface_level is not None else "auto"
        il = self.image_levels if self.image_levels is not None else est.image_levels(self.features)
        src_i = "user" if self.image_levels is not None else "auto"
        il_str = ",".join(f"{x:.4g}" for pair in il for x in pair)
        log(
            f"[spotlight] surface_level {sl:.4g} ({src_s}) -> "
            f"copick spotlight surface_level {sl:.4g}"
        )
        log(
            f"[spotlight] image_levels {il_str} ({src_i}) -> "
            f"copick spotlight image_levels {il_str}"
        )

    # ------------------------------------------------------------------- update path

    def on_active_particle(self, pos_xyz):
        """Entry point from CopickTool.focus_particle (physical/scene coords in Å)."""
        if not self.enabled:
            return
        self._center = tuple(float(x) for x in pos_xyz)
        self._request_update(self._center)

    def _on_selection(self, _trig_name, _data):
        """SELECTION_CHANGED handler: map a 3D marker click to the active particle."""
        if not self.enabled:
            return
        from chimerax.markers import selected_markers

        atoms = selected_markers(self.session)
        if len(atoms) == 0:
            return
        marker = atoms[-1]
        pid = getattr(marker, "particle_id", None)
        if pid is None:
            return

        tool = self.tool
        if pid == tool._active_particle:
            # Already active; the active_particle setter re-selects the marker, which
            # re-fires this trigger — this check terminates the loop.
            return
        if pid not in tool.stepper_list:
            self._dbg(f"selection: particle {pid} not in active list — ignored")
            return

        self._dbg(f"selection -> particle {pid}")
        tool.active_particle = tool.stepper_list.index(pid)

    def _request_update(self, center):
        if not self.enabled:
            return
        if self._worker_active:
            self._pending_center = center
            self._dbg("update pending (worker busy)")
            return
        self._start_worker(center)

    def _start_worker(self, center):
        vol = self._source_volume()
        if vol is None:
            return

        center_local = vol.scene_position.inverse() * np.asarray(center, dtype=np.float64)
        bounding = vol.bounding_region(
            [center_local], padding=self.radius, step=vol.region[2], clamp=True
        )
        # region_matrix snaps the region origin to step multiples; snap here so the
        # distance grid and the new grid's origin match the returned matrix exactly.
        ijk_origin, ijk_size, ijk_step = vol.step_aligned_region(bounding)
        if min(ijk_size) <= 0:
            self._dbg("empty region — particle outside the volume?")
            return
        region = (
            tuple(int(i) for i in ijk_origin),
            tuple(int(o + s - 1) for o, s in zip(ijk_origin, ijk_size)),
            tuple(int(i) for i in ijk_step),
        )
        center_ijk = tuple(float(x) for x in vol.data.xyz_to_ijk(center_local))

        args = (
            vol,
            region,
            center_ijk,
            tuple(float(s) for s in vol.data.step),
            float(self.radius),
            bool(self.weighted),
            float(self._fill),
        )

        self._worker_active = True
        self._seq += 1
        if self._threaded:
            worker = _compute_spotlight(*args)
            worker.returned.connect(partial(self._on_worker_returned, self._seq))
            worker.errored.connect(self._on_worker_errored)
            worker.start()
        else:
            try:
                result = _compute_spotlight_impl(*args)
            except Exception as e:
                self._on_worker_errored(e)
                return
            self._on_worker_returned(self._seq, result)

    def _on_worker_returned(self, seq, result):
        self._worker_active = False
        if not self.enabled or result is None:
            self._pending_center = None
            return
        if seq == self._seq:
            self._apply(*result)
        pending = self._pending_center
        self._pending_center = None
        if pending is not None:
            self._request_update(pending)

    def _on_worker_errored(self, exc):
        self._worker_active = False
        self.session.logger.warning(f"Spotlight update failed: {exc}")
        pending = self._pending_center
        self._pending_center = None
        if pending is not None and self.enabled:
            self._request_update(pending)

    def _apply(self, out, origin, step, elapsed_ms):
        """Main thread: push the computed array into the spotlight volume.

        The volume is kept hidden while it is mutated and its geometry is rebuilt
        synchronously (update_drawings) before it is shown again, so no frame can
        catch the model in a half-moved state.
        """
        if self._vol is not None and self._vol.deleted:
            self._vol = None
            self._grid = None

        inplace = (
            self._inplace
            and self._grid is not None
            and self._vol is not None
            and self._grid.array.shape == out.shape
            and tuple(self._grid.step) == tuple(step)
        )

        prev_updating = self._updating_style
        self._updating_style = True
        try:
            if inplace:
                v = self._vol
                v.display = False
                self._grid.array[:] = out
                self._grid.set_origin(origin)
                self._grid.values_changed()
                v.update_drawings()
                v.display = True
            else:
                if self._vol is not None and not self._vol.deleted:
                    self._vol.delete()
                self._vol = None
                self._grid = None

                src = self._source_volume()
                cell_angles = src.data.cell_angles if src else (90, 90, 90)
                rotation = src.data.rotation if src else ((1, 0, 0), (0, 1, 0), (0, 0, 1))

                from chimerax.map import volume_from_grid_data
                from chimerax.map_data import ArrayGridData

                g = ArrayGridData(
                    out,
                    origin=origin,
                    step=step,
                    cell_angles=cell_angles,
                    rotation=rotation,
                    name="spotlight",
                )
                # open_model=False: fully position and style the volume before it
                # enters the scene, so it never renders in an intermediate state.
                v = volume_from_grid_data(
                    g, self.session, style=None, open_model=False, show_dialog=False
                )
                # Let clicks pass through to particle markers inside the sphere.
                v.pickable = False
                self._grid = g
                self._vol = v
                self._apply_render_mode()
                v.update_drawings()
                v.display = True
                self.session.models.add([v])
                v.add_volume_change_callback(self._on_volume_changed)
        finally:
            self._updating_style = prev_updating

        if self.hide_particles and self._center is not None:
            self._update_particle_masks(self._center)

        c = self._center or (0, 0, 0)
        self._dbg(
            f"update center=({c[0]:.0f},{c[1]:.0f},{c[2]:.0f}) shape={out.shape} "
            f"in-place={inplace} t={elapsed_ms:.0f}ms"
        )

    # ------------------------------------------------------------------- rendering

    def _raw_surface_level(self) -> float:
        if self.surface_level is not None:
            return self.surface_level
        return self._estimator.surface_level(self.features)

    def _raw_image_levels(self) -> List[Tuple[float, float]]:
        if self.image_levels is not None:
            return self.image_levels
        return self._estimator.image_levels(self.features)

    def _effective_surface_level(self) -> float:
        lvl = self._raw_surface_level()
        wrong_side = lvl >= self._fill if self.features == "dark" else lvl <= self._fill
        if wrong_side and not self._warned_level:
            self._warned_level = True
            self.session.logger.warning(
                f"Spotlight: surface_level {lvl:.4g} is on the background side of the "
                f"mean ({self._fill:.4g}) for features={self.features} — nothing (or "
                f"everything) will be shown. See 'copick spotlight report' for suggestions."
            )
        return lvl

    def _apply_render_mode(self):
        v = self._vol
        if v is None or v.deleted:
            return

        prev_updating = self._updating_style
        self._updating_style = True
        try:
            fcolor = self._custom_color or _feature_rgba(self.session)
            if self.mode in ("surface", "mesh"):
                # cap_faces off: with a below-mean threshold the background region
                # encloses the features, and caps would draw the whole region boundary
                # as box faces. flip_normals orients lighting correctly for negative
                # (below-mean) levels.
                v.set_parameters(
                    maximum_intensity_projection=False,
                    surface_levels=[self._effective_surface_level()],
                    surface_colors=[fcolor],
                    cap_faces=False,
                    flip_normals=(self.features == "dark"),
                )
                v.set_display_style(self.mode)
            else:
                # For dark features the ramp descends with value; extend the colormap on
                # both ends so values beyond the ramp keep the end brightness (the left
                # end is near-full opacity for dark features and off by default in
                # ChimeraX).
                levels = sorted(self._raw_image_levels())
                v.set_parameters(
                    image_levels=levels,
                    image_colors=[fcolor] * len(levels),
                    image_mode="full region",
                    color_mode="auto8",
                    colormap_extend_left=True,
                    colormap_extend_right=True,
                    maximum_intensity_projection=(self.mode == "mip"),
                )
                v.set_display_style("image")
        finally:
            self._updating_style = prev_updating
        self._dbg(f"render mode -> {self.mode}")

    def _on_volume_changed(self, v, reason):
        """Adopt manual edits to the spotlight volume (volume viewer curve/threshold/
        style changes) into the spotlight configuration so they survive updates."""
        if self._updating_style or not self.enabled or v is not self._vol or v.deleted:
            return

        if reason == "thresholds changed":
            if v.image_shown and len(v.image_levels) > 0:
                self.image_levels = [tuple(l) for l in v.image_levels]
                self._dbg(f"adopted image_levels {self.image_levels}")
            elif v.surface_shown and len(v.surfaces) > 0:
                self.surface_level = float(v.surfaces[0].level)
                self._warned_level = False
                self._dbg(f"adopted surface_level {self.surface_level:.4g}")

        elif reason == "colors changed":
            if v.image_shown and len(v.image_colors) > 0:
                self._custom_color = tuple(v.image_colors[0])
            elif v.surface_shown and len(v.surfaces) > 0:
                self._custom_color = tuple(v.surfaces[0].rgba)
            if self._custom_color is not None:
                self._dbg(f"adopted color {tuple(round(c, 3) for c in self._custom_color)}")

        elif reason in ("display style changed", "rendering options changed"):
            new_mode = None
            if v.image_shown or v._style_when_shown == "image":
                new_mode = (
                    "mip" if v.rendering_options.maximum_intensity_projection else "volume"
                )
            elif v.surface_shown and len(v.surfaces) > 0:
                new_mode = "mesh" if v.surfaces[0].show_mesh else "surface"
            if new_mode is not None and new_mode != self.mode:
                self.mode = new_mode
                self.tool.settings.spotlight_mode = new_mode
                self._dbg(f"adopted mode {new_mode}")

    # -------------------------------------------------------------------- particles

    def _update_particle_masks(self, center):
        """Show only particles inside the spotlight sphere (all loaded lists)."""
        r2max = self.radius * self.radius
        cx, cy, cz = center
        for pl in self.tool.picks_map.values():
            if pl is None or pl.deleted:
                continue
            ids = pl.particle_ids
            mask = np.zeros(len(ids), dtype=bool)
            for idx, pid in enumerate(ids):
                p = pl.data[pid]
                dx = p["pos_x"] - cx
                dy = p["pos_y"] - cy
                dz = p["pos_z"] - cz
                mask[idx] = dx * dx + dy * dy + dz * dz <= r2max
            pl.displayed_particles = mask

    def _particles_show_all(self):
        """Show all particles of all loaded lists (the spotlight-mode default)."""
        for pl in self.tool.picks_map.values():
            if pl is None or pl.deleted:
                continue
            pl.displayed_particles = True

    # ---------------------------------------------------------------------- helpers

    def _source_volume(self):
        tool = self.tool
        if tool.active_volume is None or tool.active_volume.deleted:
            return None
        return tool.active_volume

    def _active_particle_position(self):
        artia = getattr(self.session, "ArtiaX", None)
        tool = self.tool
        if artia is None or tool._active_particle is None:
            return None
        pl = artia.partlists.get(artia.options_partlist)
        if pl is None or tool._active_particle not in pl.data:
            return None
        p = pl.data[tool._active_particle]
        return (p["pos_x"], p["pos_y"], p["pos_z"])

    def _dbg(self, msg):
        if self.debug:
            self.session.logger.info(f"[spotlight] {msg}")
