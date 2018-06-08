# vim: set expandtab shiftwidth=4 softtabstop=4:

# === UCSF ChimeraX Copyright ===
# Copyright 2016 Regents of the University of California.
# All rights reserved.  This software provided pursuant to a
# license agreement containing restrictions on its disclosure,
# duplication and use.  For details see:
# http://www.rbvi.ucsf.edu/chimerax/docs/licensing.html
# This notice must be embedded in or attached to all copies,
# including partial copies, of the software or any revisions
# or derivations thereof.
# === UCSF ChimeraX Copyright ===

def open(session, filename, format=None, name=None, from_database=None, ignore_cache=False, **kw):
    '''Open a file.

    Parameters
    ----------
    filename : string or list of strings
        A path to a file (relative to the current directory), or a database id
        code to fetch prefixed by the database name, for example, pdb:1a0m,
        mmcif:1jj2, emdb:1080.  A 4-letter id that is not a local file is
        interpreted as an mmCIF fetch.  Also allows a list of filenames and ids.
    format : string
        Read the file using this format, instead of using the file suffix to
        infer the format.
    name : string
        Name to use for data set.  If none specified then filename is used.
    from_database : string
        Database to fetch from. The filename is treated as a database
        identifier.
    ignore_cache : bool
        Whether to fetch files from cache.  Fetched files are always written
        to cache.
    '''

    if isinstance(filename, list):
        models = []
        for fname in filename:
            models.extend(open(session, fname, format=format, name=name,
                               from_database=from_database, ignore_cache=ignore_cache, **kw))
        return models
    if ':' in filename:
        prefix, fname = filename.split(':', maxsplit=1)
        from chimerax.core import fetch
        from_database, default_format = fetch.fetch_from_prefix(prefix)
        if from_database is not None:
            if format is None:
                format = default_format
            filename = fname
    elif from_database is None:
        # Accept 4 character filename without prefix as pdb id.
        from os.path import splitext
        base, ext = splitext(filename)
        if not ext and len(filename) == 4:
            from_database = 'pdb'
            if format is None:
                format = 'mmcif'

    def handle_unknown_kw(f, *args, **kw):
        try:
            return f(*args, **kw)
        except TypeError as e:
            if 'unexpected keyword' in str(e):
                from chimerax.core.errors import UserError
                raise UserError(str(e))
            raise
    from chimerax.core.filehistory import remember_file
    if from_database is not None:
        from chimerax.core import fetch
        if format is not None:
            db_formats = fetch.database_formats(from_database)
            if format not in db_formats:
                from chimerax.core.errors import UserError
                from chimerax.core.commands import commas, plural_form
                raise UserError(
                    'Only %s %s can be fetched from %s database'
                    % (commas(['"%s"' % f for f in db_formats], ' and '),
                       plural_form(db_formats, "format"), from_database))
        models, status = handle_unknown_kw(fetch.fetch_from_database, session, from_database,
            filename, format=format, name=name, ignore_cache=ignore_cache, **kw)
        if len(models) > 1:
            session.models.add_group(models)
        else:
            session.models.add(models)
        show_citations(session, models)
        remember_file(session, filename, format, models, database=from_database, open_options = kw)
        session.logger.status(status, log=True)
        return models

    if format is not None:
        fmt = format_from_name(format)
        if fmt:
            format = fmt.name
        else:
            from chimerax.core.errors import UserError
            raise UserError('Unknown format "%s", or no support for opening this format.' % format)

    from os.path import exists
    if exists(filename):
        paths = [filename]
    else:
        from glob import glob
        paths = glob(filename)
        paths.sort()	# python glob does not sort. Keep series in order.
        if len(paths) == 0:
            from chimerax.core.errors import UserError
            raise UserError('File not found: %s' % filename)

    try:
        models = handle_unknown_kw(session.models.open, paths, format=format, name=name, **kw)
    except OSError as e:
        from chimerax.core.errors import UserError
        raise UserError(e)
    show_citations(session, models)
    
    # Remember in file history
    rfmt = None if format is None else fmt.nicknames[0]
    remember_file(session, filename, rfmt, models or 'all models', open_options = kw)

    return models

def format_from_name(name, open=True, save=False):
    from chimerax.core import io
    formats = [f for f in io.formats()
               if (name in f.nicknames or name == f.name) and
               ((open and f.open_func) or (save and f.export_func))]
    if formats:
        return formats[0]
    return None


def show_citations(session, models):
    from chimerax.core.atomic.mmcif import citations
    c_tmp = []
    for m in models:
        c = citations(m, only='primary')
        if c:
            c_tmp.append((m.name, c))
    cites = []
    for c in c_tmp:
        if c and c not in cites:
            cites.append(c)
    if cites:
        from html import escape
        info = '<dl>'
        info += ''.join('<dt>%s citation:<dd>%s' % (escape(n), '<p>'.join(c)) for (n, c) in cites)
        info += '</dl>'
        session.logger.info(info, is_html=True)


def open_formats(session):
    '''Report file formats, suffixes and databases that the open command knows about.'''
    if session.ui.is_gui:
        lines = ['<table border=1 cellspacing=0 cellpadding=2>', '<tr><th>File format<th>Short name(s)<th>Suffixes']
    else:
        session.logger.info('File format, Short name(s), Suffixes:')
    from chimerax.core import io
    from chimerax.core.commands import commas
    formats = list(f for f in io.formats() if f.open_func is not None)
    formats.sort(key = lambda f: f.name.lower())
    for f in formats:
        if session.ui.is_gui:
            from html import escape
            if f.reference:
                descrip = '<a href="%s">%s</a>' % (f.reference, escape(f.synopsis))
            else:
                descrip = escape(f.synopsis)
            lines.append('<tr><td>%s<td>%s<td>%s' % (descrip,
                escape(commas(f.nicknames)), escape(', '.join(f.extensions))))
        else:
            session.logger.info('    %s: %s: %s' % (f.synopsis,
                commas(f.nicknames), ', '.join(f.extensions)))
    if session.ui.is_gui:
        lines.append('</table>')
        lines.append('<p></p>')

    if session.ui.is_gui:
        lines.extend(['<table border=1 cellspacing=0 cellpadding=2>', '<tr><th>Database<th>Formats'])
    else:
        session.logger.info('\nDatabase, Formats:')
    from chimerax.core.fetch import fetch_databases
    databases = list(fetch_databases().values())
    databases.sort(key=lambda k: k.database_name)
    for db in databases:
        if db.default_format is None:
            continue
        formats = list(db.fetch_function.keys())
        formats.sort()
        formats.remove(db.default_format)
        formats.insert(0, db.default_format)
        if not session.ui.is_gui:
            session.logger.info('    %s: %s' % (db.database_name, ', '.join(formats)))
            continue
        line = '<tr><td>%s<td>%s' % (db.database_name, ', '.join(formats))
        pf = [(p, f) for p, f in db.prefix_format.items()
              if p != db.database_name]
        if pf:
            line += '<td>' + ', '.join('prefix %s fetches format %s' % (p, f) for p, f in pf)
        lines.append(line)
    if session.ui.is_gui:
        lines.append('</table>')
        msg = '\n'.join(lines)
        session.logger.info(msg, is_html=True)


def register_command(logger):
    from chimerax.core.commands import CmdDesc, register, DynamicEnum, StringArg, BoolArg, \
        OpenFileNameArg, RepeatOf

    def formats():
        from chimerax.core import io, fetch
        names = set()
        for f in io.formats():
            names.update(f.nicknames)
        for db in fetch.fetch_databases():
            formats = list(fetch.database_formats(db))
            if formats and formats[0] is not None:
                names.update(formats)
        return names

    def db_formats():
        from chimerax.core import fetch
        return [f.database_name for f in fetch.fetch_databases().values()]
    desc = CmdDesc(
        required=[('filename', RepeatOf(OpenFileNameArg))],
        keyword=[
            ('format', DynamicEnum(formats)),
            ('name', StringArg),
            ('from_database', DynamicEnum(db_formats)),
            ('ignore_cache', BoolArg),
            # ('id', ModelIdArg),
        ],
        synopsis='read and display data')
    register('open', desc, open, logger=logger)
    of_desc = CmdDesc(synopsis='report formats that can be opened')
    register('open formats', of_desc, open_formats, logger=logger)
