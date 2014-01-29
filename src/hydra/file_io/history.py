# Keep list of recently accessed files and thumbnail images.
class File_History:

  def __init__(self, session, history_file = None):

    self.session = session

    if history_file is None:
      from os.path import join
      history_file = self.recent_files_index()

    self.history_file = history_file
    from os.path import dirname, join
    self.thumbnail_directory = join(dirname(history_file), 'images')
    self.read = False
    self.changed = False
    self.files = {}             # Path to (access_time, image_name)
    self.thumbnail_size = 256
    self.image_format = 'JPG'
    self.render_cb = None

    session.at_quit(self.write_history)

  def read_history(self, remove_missing = True):

    hfile = self.history_file
    from os.path import join, isfile
    if not isfile(hfile):
      if not self.install_example_sessions(hfile):
        return

    f = open(hfile, 'r')
    lines = f.readlines()
    f.close()

    files = {}
    for line in lines:
      fields = line.rstrip().split('|')
      spath,iname = fields[:2]
      atime = int(fields[2])
      files[spath] = (atime, iname)

    if remove_missing:
      removed_some = False
      for spath, (atime,iname) in tuple(files.items()):
        if not isfile(spath):
          files.pop(spath)
          removed_some = True
      if removed_some:
        self.changed = True

    self.read = True

    self.files = files

  def install_example_sessions(self, hfile):

    from os.path import dirname, join, exists
    from os import mkdir, listdir

    sdir = join(dirname(hfile), 'example_sessions')
    if exists(sdir):
      return False

    # Make directory for example sessions
    mkdir(sdir)

    # Make thumbnail images directory
    if not exists(self.thumbnail_directory):
      mkdir(self.thumbnail_directory)

    import hydra
    esdir = join(dirname(hydra.__file__), 'example_sessions')
    f = open(join(esdir, 'sessions'), 'r')
    slines = f.readlines()
    f.close()

    # Copy example sessions and thumbnail images and write history file.
    sfile = open(hfile, 'a')
    from shutil import copyfile
    for line in slines:
      fields = line.split('|')
      if len(fields) == 3:
        sname, iname, atime = [f.strip() for f in fields]
        copyfile(join(esdir,sname), join(sdir,sname))
        copyfile(join(esdir,iname), join(self.thumbnail_directory,iname))
        sfile.write('%s|%s|%s\n' % (join(sdir,sname), iname, atime))
    sfile.close()

    return True

  def write_history(self):

    if not self.changed:
      return

    from os.path import basename
    f = open(self.history_file, 'w')
    f.write('\n'.join('%s|%s|%d' % (spath,iname,atime)
                      for spath,atime,iname in self.files_sorted_by_access_time()))
    f.close()

  def files_sorted_by_access_time(self):

    s = [(spath, atime, iname) for spath,(atime,iname) in self.files.items()]
    s.sort(key = lambda sai: sai[1])
    s.reverse()
    return s

  def add_entry(self, path, replace_image = False, wait_for_render = False):

    if not self.read:
      self.read_history()

    atime,iname = self.files.get(path, (None,None))
    v = self.session.view
    if iname is None:
      from os.path import splitext, basename
      bname = splitext(basename(path))[0] + '.' + self.image_format.lower()
      iname = unique_file_name(bname, self.thumbnail_directory)
      self.save_thumbnail(iname, v, wait_for_render)
    elif replace_image:
      self.save_thumbnail(iname, v, wait_for_render)

    from time import time
    atime = time()

    self.files[path] = (atime,iname)
    self.changed = True

  def save_thumbnail(self, iname, viewer, wait_for_render = False):

    if self.render_cb:
      viewer.remove_rendered_frame_callback(self.render_cb)
      self.render_cb = None

    if wait_for_render and viewer.redraw_needed:
      self.render_cb = cb = lambda s=self,i=iname,v=viewer: s.save_thumbnail(i,v)
      viewer.add_rendered_frame_callback(cb)
    else:
      from os.path import join
      ipath = join(self.thumbnail_directory, iname)
      s = self.thumbnail_size
      i = viewer.image(s,s)
      i.save(ipath, self.image_format)

  def recent_files_index(self):

    return user_settings_path('recent_files')

  def show_thumbnails(self):

    mw = self.session.main_window
    if self.history_shown():
      mw.show_graphics()
      return

    if not self.read:
      self.read_history()
    
    mw.show_text(self.html(), html=True, id = 'recent sessions',
                 anchor_callback = self.open_clicked_session)

  def open_clicked_session(self, url):

    path = url.toString(url.PreferLocalFile)         # session file path
    import os.path
    if not os.path.exists(path):
      self.session.show_status('Session file not found: %s' % path)
      return
    self.hide_history()
    from . import opensave
    opensave.open_session(path, self.session)

  def history_shown(self):

    mw = self.session.main_window
    return mw.showing_text() and mw.text_id == 'recent sessions'

  def hide_history(self):

    mw = self.session.main_window
    mw.show_graphics()

  def most_recent_directory(self):

    if not self.read:
      self.read_history()
    if len(self.files) == 0:
      return None
    p, atime, iname = self.files_sorted_by_access_time()[0]
    from os.path import dirname
    return dirname(p)
    
  def html(self):

    from os.path import basename, splitext, join
    lines = ['<html>', '<head>', '<style>',
             'body { background-color: black; }',
             'a { text-decoration: none; }',      # No underlining of links
             'a:link { color: #FFFFFF; }',        # Link text color white.
             'table { float:left; }',             # Multiple image/caption tables per row.
             'td { font-size:large; }',
             #           'td { text-align:center; }',        # Does not work in Qt 5.0.2
             '</style>', '</head>', '<body>']
    s = self.files_sorted_by_access_time()
    for spath, atime, iname in s:
      sname = splitext(basename(spath))[0]
      ipath = join(self.thumbnail_directory, iname)
      lines.extend(['',
                    '<a href="%s">' % spath,
                    '<table style="float:left;">',
                    '<tr><td><img src="%s" height=180>' % ipath,
                    '<tr><td><center>%s</center>' % sname,
                    '</table>',
                    '</a>'])
    lines.extend(['</body>', '</html>'])
    html = '\n'.join(lines)
    return html

def unique_file_name(name, directory):
  from os.path import join, dirname, splitext, basename, isfile
  bname, suffix = splitext(name)
  uname = name
  upath = join(directory, uname)
  n = 1
  while isfile(upath):
    uname = '%s%d%s' % (bname, n, suffix)
    upath = join(directory, uname)
    n += 1
  return uname

def user_settings_path(filename = None, directory = False):
  from ..ui.qt import QtCore
  data_dir = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.GenericDataLocation)
  from os.path import isdir, join
  if not isdir(data_dir):
    return None
  c2_dir = join(data_dir, 'Hydra')
  if not isdir(c2_dir):
    import os
    os.mkdir(c2_dir)
  if filename is None:
    return c2_dir
  fpath = join(c2_dir, filename)
  if directory and not isdir(fpath):
    import os
    os.mkdir(fpath)
  return fpath
