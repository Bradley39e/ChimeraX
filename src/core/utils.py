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

"""
utils: Generically useful stuff that doesn't fit elsewhere
==========================================================
"""
import sys


# Based on Mike C. Fletcher's BasicTypes library
# https://sourceforge.net/projects/basicproperty/ and comments in
# http://rightfootin.blogspot.com/2006/09/more-on-python-flatten.html
# Except called flattened, like sorted, since it is nondestructive
def flattened(input, *, return_types=(list, tuple, set), return_type=None, maxsize=sys.maxsize):
    """Return new flattened version of input

    Parameters
    ----------
    input : a sequence instance (list, tuple, or set)
    return_type : optional return type (defaults to input type)

    Returns
    -------
    A sequence of the same type as the input.
    """
    if return_type is None:
        return_type = type(input)
        if return_type not in return_types:
            return_type = list  # eg., not zip
    output = list(input)
    try:
        # for every possible index
        for i in range(maxsize):
            # while that index currently holds a list
            while isinstance(output[i], return_types):
                # expand that list into the index (and subsequent indicies)
                output[i:i + 1] = output[i]
    except IndexError:
        pass
    if return_type == list:
        return output
    return return_type(output)


_ssl_init_done = False


def initialize_ssl_cert_dir():
    """Initialize OpenSSL's CA certificates file.

    Makes it so certificates can be verified.
    """
    global _ssl_init_done
    if _ssl_init_done:
        return
    _ssl_init_done = True

    if not sys.platform.startswith('linux'):
        return
    import os
    import ssl
    dvp = ssl.get_default_verify_paths()
    # from https://golang.org/src/crypto/x509/root_linux.go
    cert_files = [
        "/etc/ssl/certs/ca-certificates.crt",  # Debian/Ubuntu/Gentoo etc.
        "/etc/pki/tls/certs/ca-bundle.crt",    # Fedora/RHEL 6
        "/etc/ssl/ca-bundle.pem",              # OpenSUSE
        "/etc/pki/tls/cacert.pem",             # OpenELEC
        "/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem",  # CentOS/RHEL 7
    ]
    for fn in cert_files:
        if os.path.exists(fn):
            os.environ[dvp.openssl_cafile_env] = fn
            # os.environ[dvp.openssl_capath_env] = os.path.dirname(fn)
            return


def can_set_file_icon():
    '''Can an icon image be associated with a file on this operating system.'''
    from sys import platform
    return platform == 'darwin'


def set_file_icon(path, image):
    '''Assoicate an icon image with a file to be shown by the operating system file browser.'''
    if not can_set_file_icon():
        return

    # Encode image as jpeg.
    import io
    f = io.BytesIO()
    image.save(f, 'JPEG')
    s = f.getvalue()

    from . import _mac_util
    _mac_util.set_file_icon(path, s)

def string_to_attr(string, *, prefix="", collapse=True):
    """Convert an arbitrary string into a legal Python identifier

       'string' is the string to convert

       'prefix' is a string to prepend to the result

       'collapse' controls whether consecutive underscores are collapsed into one

       If there is no prefix and the string begins with a digit, an underscore will be prepended
    """
    if not string:
        raise ValueError("Empty string to convert to attr name")
    attr_name = prefix
    for c in string:
        if not c.isalnum():
            if attr_name.endswith('_') and collapse:
                continue
            attr_name += '_'
        else:
            attr_name += c
    if attr_name[0].isdigit():
        attr_name = "_" + attr_name
    return attr_name
