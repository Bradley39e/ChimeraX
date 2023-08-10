from chimerax.map.volume import (
    set_initial_region_and_style, show_volume_dialog
    , MultiChannelSeries, MapChannelsModel, default_settings, set_data_cache
    , data_already_opened, any_volume_open, _reset_color_sequence
    , set_initial_volume_color, Volume
)

from ..types import Axis

from . import modality
from .dicom_models import DicomGrid

class DICOMVolume(Volume):
    def __init__(self, session, grid_data, rendering_options = None):
        Volume.__init__(self, session, grid_data, rendering_options=rendering_options)

    def is_segmentation(self):
        try:
            return self.data.dicom_data.modality == modality.Segmentation
        except AttributeError:
            # TODO: This is a hack to get around the fact that there is no DICOM data
            # in a segmentation
            return True

    def set_segment_data(self, axis: Axis, slice: int, positions, value: int) -> None:
        for position in positions:
            center_x, center_y, radius = position
            self.set_data_in_puck(axis, slice, round(center_x), round(center_y), radius, value)
        self.data.values_changed()

    def set_data_in_puck(self, axis: Axis, slice: int, left_offset: int, bottom_offset: int, radius: int, value: int) -> None:
        # TODO: if not segmentation, refuse
        # TODO: Preserve the happiest path. If the radius of the segmentation overlay is
        #  less than the radius of one voxel, there's no need to go through all the rigamarole.
        #  grid.data.segment_array[slice][left_offset][bottom_offset] = 1
        x_max, y_max, z_max = self.data.size
        x_step, y_step, z_step = self.data.step
        if axis == Axis.AXIAL:
            slice = self.data.pixel_array[slice]
            vertical_max = y_max - 1
            vertical_step = y_step
            horizontal_max = x_max - 1
            horizontal_step = x_step
        elif axis == Axis.CORONAL:
            slice = self.data.pixel_array[:, slice, :]
            vertical_max = z_max - 1
            vertical_step = z_step
            horizontal_max = x_max - 1
            horizontal_step = x_step
        else:
            slice = self.data.pixel_array[:, :, slice]
            vertical_max = z_max - 1
            vertical_step = z_step
            horizontal_max = y_max - 1
            horizontal_step = y_step
        scaled_radius = round(radius / horizontal_step)
        x = 0
        y = round(radius)
        d = 1 - y
        while y > x:
            if d < 0:
                d += 2 * x + 3
            else:
                d += 2 * (x - y) + 5
                y -= 1
            x += 1
            scaled_horiz_x = round(x / horizontal_step)
            scaled_vert_x = round(x / vertical_step)
            scaled_horiz_y = round(y / horizontal_step)
            scaled_vert_y = round(y / vertical_step)
            x_start = round(max(left_offset - scaled_horiz_x, 0))
            x_end = round(min(left_offset + scaled_horiz_x, horizontal_max))
            y_start = round(max(bottom_offset - scaled_vert_y, 0))
            y_end = round(min(bottom_offset + scaled_vert_y, vertical_max))
            slice[y_start][x_start:x_end] = value
            slice[y_end][x_start:x_end] = value
            # Try to account for the fact that with spacings < 1 some lines get skipped, even if it
            # causes redundant writes
            slice[y_start + 1][x_start:x_end] = value
            slice[y_end - 1][x_start:x_end] = value
            x_start = round(max(left_offset - scaled_horiz_y, 0))
            x_end = round(min(left_offset + scaled_horiz_y, horizontal_max))
            y_start = round(max(bottom_offset - scaled_vert_x, 0))
            y_end = round(min(bottom_offset + scaled_vert_x, vertical_max))
            slice[y_start][x_start:x_end] = value
            slice[y_end][x_start:x_end] = value
            # Try to account for the fact that with spacings < 1 some lines get skipped, even if it
            # causes redundant writes
            slice[y_start + 1][x_start:x_end] = value
            slice[y_end - 1][x_start:x_end] = value
        slice[bottom_offset][left_offset - scaled_radius:left_offset + scaled_radius] = value

    def set_data_in_sphere(self, center: tuple, radius: int, value: int) -> None:
        ...

    def set_step(self, step: int) -> None:
        ijk_min = self.region[0]
        ijk_max = self.region[1]
        ijk_step = [step, step, step]
        self.new_region(ijk_min, ijk_max, ijk_step, adjust_step = False)

    def segment(self, number):
        new_grid = DicomGrid(
            None, self.data.size, 'uint8'
            , self.data.origin, self.data.step, self.data.rotation
            , "", name = "segmentation %d" % number, time = None, channel = None
        )
        new_grid.reference_data = self.data
        new_seg_model = open_dicom_grids(self.session, [new_grid], name = "new segmentation")[0]
        self.session.models.add(new_seg_model)
        new_seg_model[0].set_parameters(surface_levels=[0.501])
        new_seg_model[0].set_step(1)
        return new_seg_model[0]

def dicom_volume_from_grid_data(grid_data, session, style = 'auto',
                          open_model = True, model_id = None, show_dialog = True):
    '''
    Supported API.
    Create a new :class:`.Volume` model from a :class:`~.data.GridData` instance and set its initial
    display style and color and add it to the session open models.

    Parameters
    ----------
    grid_data : :class:`~.data.GridData`
      Use this GridData to create the Volume.
    session : :class:`~chimerax.core.session.Session`
      The session that the Volume will belong to.
    style : 'auto', 'surface', 'mesh' or 'image'
      The initial display style.
    open_model : bool
      Whether to add the Volume to the session open models.
    model_id : tuple of integers
      Model id for the newly created Volume.
      It is an error if the specifid id equals the id of an existing model.
    show_dialog : bool
      Whether to show the Volume Viewer user interface panel.

    Returns
    -------
    volume : the created :class:`.Volume`
    '''

    set_data_cache(grid_data, session)

    ds = default_settings(session)
    ro = ds.rendering_option_defaults()
    if getattr(grid_data, 'polar_values', None):
      ro.flip_normals = True
      ro.cap_faces = False
    if hasattr(grid_data, 'initial_rendering_options'):
      for oname, ovalue in grid_data.initial_rendering_options.items():
        setattr(ro, oname, ovalue)

    # Create volume model
    d = data_already_opened(grid_data.path, grid_data.grid_id, session)
    if d:
      grid_data = d

    v = DICOMVolume(session, grid_data, rendering_options = ro)

    # Set display style
    if style == 'auto':
      # Show single plane data in image style.
      single_plane = [s for s in grid_data.size if s == 1]
      style = 'image' if single_plane else 'surface'
    if style is not None:
      v._style_when_shown = style

    if grid_data.rgba is None:
      if not any_volume_open(session):
        _reset_color_sequence(session)
      set_initial_volume_color(v, session)

    if not model_id is None:
      if session.models.have_id(model_id):
        from chimerax.core.errors import UserError
        raise UserError('Tried to create model #%s which already exists'
                        % '.'.join('%d'%i for i in model_id))

      v.id = model_id

    if open_model:
      session.models.add([v])

    if show_dialog:
      show_volume_dialog(session)

    return v


def open_dicom_grids(session, grids, name, **kw):
    if kw.get('polar_values', False):
        for g in grids:
            g.polar_values = True
        if g.rgba is None:
            g.rgba = (0,1,0,1) # Green

    channel = kw.get('channel', None)
    if channel is not None:
        for g in grids:
            g.channel = channel

    series = kw.get('vseries', None)
    if series is not None:
        if series:
            for i,g in enumerate(grids):
                if tuple(g.size) != tuple(grids[0].size):
                    gsizes = '\n'.join((g.name + (' %d %d %d' % g.size)) for g in grids)
                    from chimerax.core.errors import UserError
                    raise UserError('Cannot make series from volumes with different sizes:\n%s' % gsizes)
                g.series_index = i
        else:
            for g in grids:
                if hasattr(g, 'series_index'):
                    delattr(g, 'series_index')

    maps = []
    if 'show' in kw:
        show = kw['show']
    else:
        show = (len(grids) >= 1 and getattr(grids[0], 'show_on_open', True))
    si = [d.series_index for d in grids if hasattr(d, 'series_index')]
    is_series = (len(si) == len(grids) and len(set(si)) > 1)
    cn = [d.channel for d in grids if d.channel is not None]
    is_multichannel = (len(cn) == len(grids) and len(set(cn)) > 1)
    for d in grids:
        show_data = show
        if is_series or is_multichannel:
            show_data = False	# MapSeries or MapChannelsModel classes will decide which to show
        vkw = {'show_dialog': False}
        if hasattr(d, 'initial_style') and d.initial_style in ('surface', 'mesh', 'image'):
            vkw['style'] = d.initial_style
        v = dicom_volume_from_grid_data(d, session, open_model = False, **vkw)
        maps.append(v)
        if not show_data:
            v.display = False
        set_initial_region_and_style(v)

    show_dialog = kw.get('show_dialog', True)
    if maps and show_dialog:
        show_volume_dialog(session)

    msg = ''
    if is_series and is_multichannel:
        cmaps = {}
        for m in maps:
            cmaps.setdefault(m.data.channel,[]).append(m)
        if len(set(len(cm) for cm in cmaps.values())) > 1:
            session.logger.warning('Map channels have differing numbers of series maps: %s'
                                   % ', '.join('%d (%d)' % (c,cm) for c, cm in cmaps.items()))
        from chimerax.map_series import MapSeries
        ms = [MapSeries('channel %d' % c, cm, session) for c, cm in cmaps.items()]
        mc = MultiChannelSeries(name, ms, session)
        models = [mc]
    elif is_series:
        from chimerax.map_series import MapSeries
        ms = MapSeries(name, maps, session)
        ms.display = show
        models = [ms]
    elif is_multichannel:
        mc = MapChannelsModel(name, maps, session)
        mc.display = show
        mc.show_n_channels(3)
        models = [mc]
    elif len(maps) == 0:
        msg = 'No map data opened'
        session.logger.warning(msg)
        models = maps
    else:
        models = maps

    # Create surfaces before adding to session so that initial view can use corrrect bounds.
    for v in maps:
        if v.display:
            v.update_drawings()

    return models, msg
