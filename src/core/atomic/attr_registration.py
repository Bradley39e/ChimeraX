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
register_attr: infrastructure for molecular classes to register custom attributes
===============================

TODO
"""

from ..state import State, StateManager

# something that can't be a default value, yet can be saved in sessions...
class _NoDefault(State):

    def take_snapshot(self, session, flags):
        return {'version':1}

    @staticmethod
    def restore_snapshot(session, data):
        return _no_default
_no_default = _NoDefault()

# methods that the manager will insert into the managed classes (inheritance won't work)
def __getattr__(self, attr_name, look_in_class=None):
    if look_in_class is None:
        look_in_class = self.__class__
    try:
        return look_in_class._attr_registration.get_attr(attr_name)
    except AttributeError:
        for base in look_in_class.__bases__:
            if hasattr(base, "__getattr__"):
                return base.__getattr__(self, attr_name, look_in_class=base)
        else:
            raise

@classmethod
def register_attr(cls, session, attr_name, registerer, default_value=_no_default, attr_type=None):
    cls._attr_registration.register(session, attr_name, registerer, default_value, attr_type)

# used within the class to hold the registration info
class AttrRegistration:
    def __init__(self, class_):
        self.reg_attr_info = {}
        self.class_ = class_
        self._session_attrs = {}
        self._ses_attr_counts = {}

    def get_attr(self, attr_name):
        try:
            registrant, default_value, attr_type = self.reg_attr_info[attr_name]
        except KeyError:
            raise AttributeError("'%s' object has no attribute '%s'" % (self.class_.__name__, attr_name))
        if default_value == _no_default:
            raise AttributeError("'%s' object has no attribute '%s'" % (self.class_.__name__, attr_name))
        return default_value

    def register(self, session, attr_name, registrant, default_value, attr_type):
        if attr_name in self.reg_attr_info:
            prev_registrant, prev_default, prev_type = self.reg_attr_info[attr_name]
            if prev_default == default_value and prev_type == attr_type:
                return
            raise ValueError("Registration of attr '%s' with %s by %s conflicts with previous"
                " registration by %s" % (attr_name, self.class_.__name__, registrant, prev_registrant))
        self.reg_attr_info[attr_name] = (registrant, default_value, attr_type)
        session_attrs = self._session_attrs.setdefault(session, set())
        if attr_name not in session_attrs:
            session_attrs.add(attr_name)
            self._ses_attr_counts[attr_name] = self._ses_attr_counts.get(attr_name, 0) + 1

    # session functions; called from manager, not directly from session-saving mechanism,
    # so API varies from that for State class
    def reset_state(self, session):
        if session not in self._session_attrs:
            return
        for attr_name in self._session_attrs[session]:
            if self._ses_attr_counts[attr_name] == 1:
                del self._ses_attr_counts[attr_name]
                del self.reg_attr_info[attr_name]
            else:
                self._ses_attr_counts[attr_name] -= 1
        del self._session_attrs[session]

    def take_snapshot(self, session, flags):
        ses_reg_attr_info = {}
        attr_names = self._session_attrs.get(session, [])
        for attr_name in attr_names:
            ses_reg_attr_info[attr_name] = self.reg_attr_info[attr_name]
        instance_data = {}
        if attr_names:
            # if no registered attrs; don't need to look at instances
            instance_data[attr_name] = per_instance_info = []
            for instance in self.class_.get_existing_instances(session):
                try:
                    attr_val = getattr(instance, attr_name)
                except AttributeError:
                    continue
                per_instance_info.append((instance, attr_val))
        data = {'reg_attr_info': ses_reg_attr_info, 'instance_data': instance_data}
        return data

    def restore_session_data(self, session, data):
        for attr_name, reg_info in data['reg_attr_info'].items():
            self.register(session, attr_name, *reg_info)
        for attr_name, per_instance_data in data['instance_data'].items():
            for instance, attr_val in per_instance_data:
                setattr(instance, attr_name, attr_val)

# used in session so that registered attributes get saved/restored
from . import Atom, AtomicStructure, Bond, CoordSet, Pseudobond, \
    PseudobondGroup, PseudobondManager, Residue, Structure

# the classes need to have a get_existing_instances static method...
registerable_classes = [ Atom, AtomicStructure, Bond, CoordSet,
    #Pseudobond,
    PseudobondGroup, PseudobondManager, Residue, Structure,
    ]

class RegAttrManager(StateManager):

    def __init__(self):
        for reg_class in registerable_classes:
            if not hasattr(reg_class, '_attr_registration'):
                reg_class._attr_registration = AttrRegistration(reg_class)
                reg_class.__getattr__ = __getattr__
                reg_class.register_attr = register_attr
        # for now, this is how we track all Sequence, etc. instances
        from weakref import WeakSet
        self._seq_instances = WeakSet()

    # session functions; there is one manager per session, and is only in charge of
    # remembering registrations from its session (actual dirty work delegated to
    # AttrRegistration instances)
    def reset_state(self, session):
        for reg_class in registerable_classes:
            reg_class._attr_registration.reset_state(session)

    def take_snapshot(self, session, flags):
        # force save of registration instance session info
        return {
            'version': 1,
            'registrations': {rc.__name__: rc._attr_registration.take_snapshot(session, flags)
                for rc in registerable_classes}
        }

    @staticmethod
    def restore_snapshot(session, data):
        inst = RegAttrManager()
        from .. import bundle_api
        for class_name, registration in data['registrations'].items():
            bundle_api.get_class(class_name)._attr_registration.restore_session_data(
                session, registration)
        return inst