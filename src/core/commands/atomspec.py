# vim: set expandtab shiftwidth=4 softtabstop=4:
"""
atomspec: atom specifier cli annotation and evaluation
======================================================

The 'atomspec' module provides two classes:

- AtomSpecArg : command line argument annotation class.
- AtomSpec : atom specifier class.

AtomSpecArg is a cli type annotation and is used to describe an
argument of a function that is registered with the cli module.  When
the registered function is called, the argument corresponding to
the AtomSpecArg is an instance of AtomSpec, which contains a parsed
version of the input atom specifier.  The model elements (atoms,
bonds, models, etc) that match an AtomSpec may be found by calling
the 'evaluate' method which returns an instance of Objects.
Each type of model elements may be accessed as an attribute of the
Objects instance.

Selectors
---------

A (name, function) pair may be registered as a 'selector' in an
atom specifier.  The selectors may either be global (e.g., chemical
groups) or session-specific (e.g., active site).  The selector
name may appear wherever a model, residue or atom string does.
The selector function is called when the atom specifier is
evaluated and is expected to fill in an Objects instance.

Example
-------

Here is an example of a function that may be registered with cli::

    from chimerax.core.commands import cli, atomspec

    def move(session, by, modelspec=None):
        if modelspec is None:
            modelspec = atomspec.everything(session)
        spec = modelspec.evaluate(session)
        import numpy
        by_vector = numpy.array(by)
        from chimerax.core.geometry import place
        translation = place.translation(by_vector)
        for m in spec.models:
            m.position = translation * m.position
    move_desc = cli.CmdDesc(required=[("by", cli.Float3Arg)],
                            optional=[("modelspec", atomspec.AtomSpecArg)])

Notes
-----

AtomSpecArg arguments should always be optional because
not providing and atom specifier is the same as choosing
all atoms.

"""

import re
from .cli import Annotation

_double_quote = re.compile(r'"(.|\")*?"(\s|$)')


class AtomSpecArg(Annotation):
    """Command line type annotation for atom specifiers.

    See cli documentation for details on type annotations.

    """
    name = "an atom specifier"
    url = "help:user/commands/atomspec.html"

    @staticmethod
    def parse(text, session):
        """Parse text and return an atomspec parse tree"""
        if not text or text[0].isspace():
            from .cli import AnnotationError
            raise AnnotationError("empty atom specifier")
        if text[0] == '"':
            return AtomSpecArg._parse_quoted(text, session)
        else:
            return AtomSpecArg._parse_unquoted(text, session)

    @staticmethod
    def _parse_quoted(text, session):
        # Split out quoted argument
        start = 0
        m = _double_quote.match(text, start)
        if m is None:
            from .cli import AnnotationError
            raise AnnotationError("incomplete quoted text")
        end = m.end()
        if text[end - 1].isspace():
            end -= 1
        # Quoted argument is consumed on success
        # Text after quote is unused
        consumed = text[start:end]
        rest = text[end:]
        # Convert quote contents to string
        from .cli import unescape_with_index_map
        token, index_map = unescape_with_index_map(text[start + 1:end - 1])
        # Create parser and parse converted token
        from ._atomspec import _atomspecParser
        parser = _atomspecParser(parseinfo=True)
        semantics = _AtomSpecSemantics(session)
        from grako.exceptions import FailedParse, FailedSemantics
        try:
            ast = parser.parse(token, "atom_specifier", semantics=semantics)
        except FailedSemantics as e:
            from .cli import AnnotationError
            raise AnnotationError(str(e), offset=e.pos)
        except FailedParse as e:
            from .cli import AnnotationError
            # Add one to offset for leading quote
            offset = index_map[e.pos]
            raise AnnotationError(str(e), offset=offset)
        # Must consume everything inside quotes
        if ast.parseinfo.endpos != len(token):
            from .cli import AnnotationError
            offset = index_map[ast.parseinfo.endpos] + 1
            raise AnnotationError("mangled atom specifier", offset=offset)
        # Success!
        return ast, consumed, rest

    @staticmethod
    def _parse_unquoted(text, session):
        # Try to parse the entire line.
        # If we get nothing, then raise AnnotationError.
        # Otherwise, consume what we can use and call it a success.
        from ._atomspec import _atomspecParser
        parser = _atomspecParser(parseinfo=True)
        semantics = _AtomSpecSemantics(session)
        from grako.exceptions import FailedParse, FailedSemantics
        try:
            ast = parser.parse(text, "atom_specifier", semantics=semantics)
        except FailedSemantics as e:
            from .cli import AnnotationError
            raise AnnotationError(str(e), offset=e.pos)
        except FailedParse as e:
            from .cli import AnnotationError
            raise AnnotationError(str(e), offset=e.pos)
        else:
            end = ast.parseinfo.endpos
            if end == 0:
                from .cli import AnnotationError
                raise AnnotationError("not an atom specifier")
            # Consume what we used and return the remainder
            return ast, text[:end], text[end:]


#
# Parsing functions and classes
#


class _AtomSpecSemantics:
    """Semantics class to convert basic ASTs into AtomSpec instances."""
    def __init__(self, session):
        self._session = session

    def atom_specifier(self, ast):
        # print("atom_specifier", ast)
        atom_spec = AtomSpec(ast.operator, ast.left, ast.right)
        try:
            atom_spec.parseinfo = ast.parseinfo
        except AttributeError:
            pass
        return atom_spec

    def as_term(self, ast):
        # print("as_term", ast)
        if ast.atomspec is not None:
            return ast.atomspec
        elif ast.tilde is not None:
            return _Invert(ast.tilde)
        elif ast.models is not None:
            return _Term(ast.models)
        else:
            return _Term(ast.selector)

    def selector_name(self, ast):
        # print("selector_name", ast)
        if (get_selector(self._session, ast.name) is None and
           get_selector(None, ast.name) is None):
                from grako.exceptions import FailedSemantics
                e = FailedSemantics("\"%s\" is not a selector name" % ast.name)
                e.pos = ast.parseinfo.pos
                e.endpos = ast.parseinfo.endpos
                raise e
        return _SelectorName(ast.name)

    def model_list(self, ast):
        # print("model_list", ast)
        model_list = _ModelList()
        if ast.model:
            model_list.extend(ast.model)
        return model_list

    def model(self, ast):
        m = _Model(ast.hierarchy, ast.attrs)
        if ast.parts is not None:
            for p in ast.parts:
                m.add_part(p)
        if ast.zone is None:
            # print("model", m)
            return m
        ast.zone.model = m
        return ast.zone

    def model_hierarchy(self, ast):
        hierarchy = _ModelHierarchy(ast.range_list)
        if ast.hierarchy:
            for rl in ast.hierarchy:
                if rl:
                    hierarchy.append(rl)
        return hierarchy

    def model_range_list(self, ast):
        range_list = _ModelRangeList(ast.range)
        if ast.range_list:
            for rl in ast.range_list:
                if rl:
                    range_list.append(rl)
        return range_list

    def model_range(self, ast):
        return _ModelRange(ast.start, ast.end)

    def model_spec(self, ast):
        if ast.number is not None:
            return int(ast.number)
        elif ast.star is not None:
            return '*'
        else:
            return None

    def model_parts(self, ast):
        return ast.chain

    def chain(self, ast):
        c = _Chain(ast.parts, ast.attrs)
        if ast.residue:
            for r in ast.residue:
                c.add_part(r)
        return c

    def residue(self, ast):
        r = _Residue(ast.parts, ast.attrs)
        if ast.atom:
            for a in ast.atom:
                r.add_part(a)
        return r

    def atom(self, ast):
        return _Atom(ast.parts, ast.attrs)

    def part_list(self, ast):
        if ast.part is None:
            return _PartList(ast.range)
        else:
            return ast.part.add_parts(ast.range)

    def part_range_list(self, ast):
        return _Part(ast.start, ast.end)

    def attr_list(self, ast):
        return _AttrList(ast)

    def attr_test(self, ast):
        return _AttrTest(ast.no, ast.name, ast.op, ast.value)

    def zone_selector(self, ast):
        operator, distance = ast
        return _ZoneSelector(operator, distance)

    def zone_operator(self, ast):
        return ast

    def real_number(self, ast):
        return float(ast)


class _ModelList(list):
    """Stores list of model hierarchies."""
    def __str__(self):
        if not self:
            return "<no model specifier>"
        return "".join(str(mr) for mr in self)

    def find_matches(self, session, model_list, results):
        for m in model_list:
            for model_spec in self:
                if model_spec.matches(session, m):
                    model_spec.find_sub_parts(session, m, results)


class _ModelHierarchy(list):
    """Stores list of model ranges in hierarchy order."""
    def __init__(self, mrl):
        super().__init__()
        self.append(mrl)

    def __str__(self):
        if not self:
            return "[empty]"
        return ".".join(str(mr) for mr in self)

    def matches(self, session, model):
        for i, mrl in enumerate(self):
            try:
                mid = model.id[i]
            except IndexError:
                return False
            if not mrl.matches(mid):
                return False
        return True


class _ModelRangeList(list):
    """Stores a list of model ranges."""
    def __init__(self, mr):
        super().__init__()
        self.append(mr)

    def __str__(self):
        if not self:
            return "[empty]"
        return ",".join(str(mr) for mr in self)

    def matches(self, mid):
        for mr in self:
            if mr.matches(mid):
                return True
        return False


class _ModelRange:
    """Stores a single model range."""
    def __init__(self, start, end):
        self.start = start
        self.end = end

    def __str__(self):
        if self.end:
            return "%s-%s" % (self.start, self.end)
        else:
            return str(self.start)

    def matches(self, mid):
        if self.end is None:
            # Exact match
            return self.start == '*' or mid == self.start
        else:
            # Range match
            if self.start != '*' and mid < self.start:
                return False
            return self.end == '*' or mid <= self.end


class _SubPart:
    """Stores part list for one item and subparts of the item."""
    def __init__(self, my_parts, my_attrs):
        self.my_parts = my_parts
        self.my_attrs = my_attrs
        self.sub_parts = None

    def __str__(self):
        if self.sub_parts:
            sub_repr = "".join([str(r) for r in self.sub_parts])
        else:
            sub_repr = ""
        if self.my_parts is None:
            r = sub_repr
        else:
            r = "%s%s%s" % (self.Symbol, str(self.my_parts), sub_repr)
        # print("_SubPart.__str__", self.__class__, r)
        return r

    def add_part(self, subpart):
        if subpart is None:
            return
        if self.sub_parts is None:
            self.sub_parts = [subpart]
        else:
            self.sub_parts.append(subpart)

    def find_selected_parts(self, model, atoms, num_atoms):
        # Only filter if a spec for this level is present
        # TODO: account for my_attrs in addition to my_parts
        if self.my_attrs is not None:
            # Using UserError instead of LimitationError to
            # avoid generating traceback in log
            from ..errors import UserError
            raise UserError("Atomspec attributes not supported yet")
        import numpy
        if self.my_parts is not None:
            my_selected = self._filter_parts(model, atoms, num_atoms)
        else:
            my_selected = numpy.ones(num_atoms)
        if self.sub_parts is None:
            return my_selected
        sub_selected = numpy.zeros(num_atoms)
        for subpart in self.sub_parts:
            s = subpart.find_selected_parts(model, atoms, num_atoms)
            sub_selected = numpy.logical_or(sub_selected, s)
        return numpy.logical_and(my_selected, sub_selected)

    def _filter_parts(self, model, atoms, num_atoms):
        return model.atomspec_filter(self.Symbol, atoms, num_atoms,
                                     self.my_parts, self.my_attrs)


class _Model(_SubPart):
    """Stores model part list and atom spec."""
    Symbol = '#'

    def matches(self, session, model):
        # TODO: account for my_attrs in addition to my_parts
        if self.my_parts is None:
            return True
        return self.my_parts.matches(session, model)

    def find_sub_parts(self, session, model, results):
        if not model.atomspec_has_atoms():
            if not self.sub_parts:
                results.add_model(model)
            return
        atoms = model.atomspec_atoms()
        if self.sub_parts:
            # Has sub-model selector, filter atoms
            import numpy
            num_atoms = len(atoms)
            selected = numpy.zeros(num_atoms)
            for chain_spec in self.sub_parts:
                s = chain_spec.find_selected_parts(model, atoms, num_atoms)
                selected = numpy.logical_or(selected, s)
            atoms = atoms.filter(selected)
        if len(atoms) > 0:
            results.add_model(model)
            results.add_atoms(atoms)


class _Chain(_SubPart):
    """Stores residue part list and atom spec."""
    Symbol = '/'


class _Residue(_SubPart):
    """Stores residue part list and atom spec."""
    Symbol = ':'


class _Atom(_SubPart):
    """Stores residue part list and atom spec."""
    Symbol = '@'


class _PartList(list):
    """Stores a part list (sub-parts of models)."""
    def __init__(self, part_range):
        super().__init__()
        self.append(part_range)

    def __str__(self):
        return ','.join([str(p) for p in self])

    def add_parts(self, part_range):
        self.insert(0, part_range)
        return self


class _Part:
    """Stores one part of a part range."""
    def __init__(self, start, end):
        self.start = start
        self.end = end

    def __str__(self):
        if self.end is None:
            return self.start
        else:
            return "%s-%s" % (self.start, self.end)


class _AttrList(list):
    """Stores a part list (sub-parts of models)."""
    def __str__(self):
        return ','.join([str(p) for p in self])


class _AttrTest:
    """Stores one part of a part range."""
    def __init__(self, no, name, op, value):
        self.no = no
        self.name = name
        self.op = op
        self.value = value

    def __str__(self):
        if self.no:
            return '~' + self.name
        elif self.op:
            return "%s%s%s" % (self.name, self.op, self.value)
        else:
            return self.name


class _SelectorName:
    """Stores a single selector name."""
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return self.name

    def find_matches(self, session, models, results):
        f = get_selector(session, self.name) or get_selector(None, self.name)
        if f:
            f(session, models, results)


class _ZoneSelector:
    """Stores zone operator and distance information."""
    def __init__(self, operator, distance):
        self.distance = distance
        self.target_type = operator[0]  # '@', ':' or '#'
        self.operator = operator[1:]    # '<', '<=', '>', '>='
        self.model = None

    def __str__(self):
        return "%s%s%.3f" % (self.target_type, self.operator, self.distance)

    def find_matches(self, session, models, results):
        if self.model is None:
            # No reference atomspec, so do nothing
            return
        return self.model.find_matches(session, models, results)

    def matches(self, session, model):
        if self.model is None:
            return False
        return self.model.matches(session, model)

    def find_sub_parts(self, session, model, results):
        if self.model is None:
            return
        from ..objects import Objects
        my_results = Objects()
        self.model.find_sub_parts(session, model, my_results)
        # TODO: expand my_results before combining with results
        results.combine(my_results)


class _Term:
    """A term in an atom specifier."""
    def __init__(self, spec):
        self._specifier = spec

    def __str__(self):
        return str(self._specifier)

    def evaluate(self, session, models):
        """Return Objects for model elements that match."""
        from ..objects import Objects
        results = Objects()
        self._specifier.find_matches(session, models, results)
        return results


class _Invert:
    """A "not" (~) term in an atom specifier."""
    def __init__(self, atomspec):
        self._atomspec = atomspec

    def __str__(self):
        return "~%s" % str(self._atomspec)

    def evaluate(self, session, models=None, **kw):
        if models is None:
            models = session.models.list(**kw)
        results = self._atomspec.evaluate(session, models)
        results.invert(session, models)
        return results


class AtomSpec:
    """AtomSpec instances store and evaluate atom specifiers.

    An AtomSpec instance, returned by AtomSpecArg arguments in
    cli command functions, keeps track of an atom specifier.
    When evaluated, the model elements that match the specifier
    are returned.
    """
    def __init__(self, operator, left_spec, right_spec):
        self._operator = operator
        self._left_spec = left_spec
        self._right_spec = right_spec

    def __str__(self):
        if self._operator is None:
            return str(self._left_spec)
        else:
            return "%s %s %s" % (str(self._left_spec), self._operator,
                                 str(self._right_spec))

    def evaluate(self, session, models=None, **kw):
        """Return results of evaluating atom specifier for given models.

        Parameters
        ----------
        session : chimerax.core.session.Session instance
            The session in which to evaluate atom specifier.
        models : list of chimerax.core.models.Model instances
            Defaults to None, which uses all models in 'session'.
        **kw : keyword arguments
            If 'models' is None, 'kw' is passed through to call to
            'session.models.list' to generate the model list.

        Returns
        -------
        Objects instance
            Instance containing data (atoms, bonds, etc) that match
            this atom specifier.
        """
        # print("evaluate:", str(self))
        if models is None:
            models = session.models.list(**kw)
        if self._operator is None:
            results = self._left_spec.evaluate(session, models)
        elif self._operator == '|':
            left_results = self._left_spec.evaluate(session, models)
            right_results = self._right_spec.evaluate(session, models)
            from ..objects import Objects
            results = Objects.union(left_results, right_results)
        elif self._operator == '&':
            left_results = self._left_spec.evaluate(session, models)
            right_results = self._right_spec.evaluate(session, models)
            from ..objects import Objects
            results = Objects.intersect(left_results, right_results)
        else:
            raise RuntimeError("unknown operator: %s" % repr(self._operator))
        return results

#
# Selector registration and use
#
# TODO: Registered session-specific selectors should go into a
# state manager class, but I have not figured out how to save
# callable objects in states.
#
_selectors = {}


def _get_selector_map(session):
    if session is None:
        return _selectors
    else:
        try:
            return session.atomspec_selectors
        except AttributeError:
            d = {}
            session.atomspec_selectors = d
            return d


def register_selector(session, name, func):
    """Register a (name, func) pair as an atom specifier selector.

    Parameters
    ----------
    session : instance of chimerax.core.session.Session
        Session in which the name may be used.  If None, name is global.
    name : str
        Selector name, preferably without whitespace.
    func : callable object
        Selector evaluation function, called as 'func(session, models, results)'
        where 'models' are chimerax.core.models.Model instances and
        'results' is an Objects instance.

    """
    if not name[0].isalpha():
        raise ValueError("registering illegal selector name \"%s\"" % name)
    for c in name[1:]:
        if not c.isalnum() and c not in "-":
            raise ValueError("registering illegal selector name \"%s\"" % name)
    _get_selector_map(session)[name] = func


def deregister_selector(session, name):
    """Deregister a name as an atom specifier selector.

    Parameters
    ----------
    session : instance of chimerax.core.session.Session
        Session in which the name may be used.  If None, name is global.
    name : str
        Previously registered selector name.

    Raises
    ------
    KeyError
        If name is not registered.

    """
    del _get_selector_map(session)[name]


def list_selectors(session):
    """Return a list of all registered selector names.

    Parameters
    ----------
    session : instance of chimerax.core.session.Session
        Session in which the name may be used.  If None, name is global.

    Returns
    -------
    iterator yielding str
        Iterator that yields registered selector names.

    """
    return _get_selector_map(session).keys()


def get_selector(session, name):
    """Return function associated with registered selector name.

    Parameters
    ----------
    session : instance of chimerax.core.session.Session
        Session in which the name may be used.  If None, name is global.
    name : str
        Previously registered selector name.

    Returns
    -------
    Callable object or None.
        Callable object if name was registered; None, if not.

    """
    return _get_selector_map(session).get(name, None)


def everything(session):
    """Return AtomSpec that matches everything.

    Parameters
    ----------
    session : instance of chimerax.core.session.Session
        Session in which the name may be used.  If None, name is global.

    Returns
    -------
    AtomSpec instance
        An AtomSpec instance that matches everything in session.
    """
    return AtomSpecArg.parse('#*', session)[0]

def all_objects(session):
    '''Return Objects that matches everything.'''
    return everything(session).evaluate(session)
