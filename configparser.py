#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Configuration file parser.

A configuration file consists of sections, lead by a "[section]" header,
and followed by "name: value" entries, with continuations and such in
the style of RFC 822.

Intrinsic defaults can be specified by passing them into the
ConfigParser constructor as a dictionary.

class:

ConfigParser -- responsible for parsing a list of
                    configuration files, and managing the parsed database.

    methods:

    __init__(defaults=None, dict_type=_default_dict, allow_no_value=False,
             delimiters=('=', ':'), comment_prefixes=('#', ';'),
             inline_comment_prefixes=None, strict=True,
             empty_lines_in_values=True):
        Create the parser. When `defaults' is given, it is initialized into the
        dictionary or intrinsic defaults. The keys must be strings, the values
        must be appropriate for %()s string interpolation.

        When `dict_type' is given, it will be used to create the dictionary
        objects for the list of sections, for the options within a section, and
        for the default values.

        When `delimiters' is given, it will be used as the set of substrings
        that divide keys from values.

        When `comment_prefixes' is given, it will be used as the set of
        substrings that prefix comments in empty lines. Comments can be
        indented.

        When `inline_comment_prefixes' is given, it will be used as the set of
        substrings that prefix comments in non-empty lines.

        When `strict` is True, the parser won't allow for any section or option
        duplicates while reading from a single source (file, string or
        dictionary). Default is True.

        When `empty_lines_in_values' is False (default: True), each empty line
        marks the end of an option. Otherwise, internal empty lines of
        a multiline option are kept as part of the value.

        When `allow_no_value' is True (default: False), options without
        values are accepted; the value presented for these is None.

    sections()
        Return all the configuration section names, sans DEFAULT.

    has_section(section)
        Return whether the given section exists.

    has_option(section, option)
        Return whether the given option exists in the given section.

    options(section)
        Return list of configuration options for the named section.

    read(filenames, encoding=None)
        Read and parse the list of named configuration files, given by
        name.  A single filename is also allowed.  Non-existing files
        are ignored.  Return list of successfully read files.

    read_file(f, filename=None)
        Read and parse one configuration file, given as a file object.
        The filename defaults to f.name; it is only used in error
        messages (if f has no `name' attribute, the string `<???>' is used).

    read_string(string)
        Read configuration from a given string.

    read_dict(dictionary)
        Read configuration from a dictionary. Keys are section names,
        values are dictionaries with keys and values that should be present
        in the section. If the used dictionary type preserves order, sections
        and their keys will be added in order. Values are automatically
        converted to strings.

    get(section, option, raw=False, vars=None, fallback=_UNSET)
        Return a string value for the named option.  All % interpolations are
        expanded in the return values, based on the defaults passed into the
        constructor and the DEFAULT section.  Additional substitutions may be
        provided using the `vars' argument, which must be a dictionary whose
        contents override any pre-existing defaults. If `option' is a key in
        `vars', the value from `vars' is used.

    getint(section, options, raw=False, vars=None, fallback=_UNSET)
        Like get(), but convert value to an integer.

    getfloat(section, options, raw=False, vars=None, fallback=_UNSET)
        Like get(), but convert value to a float.

    getboolean(section, options, raw=False, vars=None, fallback=_UNSET)
        Like get(), but convert value to a boolean (currently case
        insensitively defined as 0, false, no, off for False, and 1, true,
        yes, on for True).  Returns False or True.

    items(section=_UNSET, raw=False, vars=None)
        If section is given, return a list of tuples with (section_name,
        section_proxy) for each section, including DEFAULTSECT. Otherwise,
        return a list of tuples with (name, value) for each option
        in the section.

    remove_section(section)
        Remove the given file section and all its options.

    remove_option(section, option)
        Remove the given option from the given section.

    set(section, option, value)
        Set the given option.

    write(fp, space_around_delimiters=True)
        Write the configuration state in .ini format. If
        `space_around_delimiters' is True (the default), delimiters
        between keys and values are surrounded by spaces.
"""

from __future__ import with_statement
from collections import MutableMapping
from io import open
try:
    from collections import OrderedDict as _default_dict
except ImportError:
    from ordereddict import OrderedDict as _default_dict
import functools
import io
import itertools
import re
import sys
import warnings

from configparser_helpers import _ChainMap

__all__ = [u"NoSectionError", u"DuplicateOptionError", u"DuplicateSectionError",
           u"NoOptionError", u"InterpolationError", u"InterpolationDepthError",
           u"InterpolationSyntaxError", u"ParsingError",
           u"MissingSectionHeaderError",
           u"ConfigParser", u"SafeConfigParser", u"RawConfigParser",
           u"DEFAULTSECT", u"MAX_INTERPOLATION_DEPTH"]

DEFAULTSECT = u"DEFAULT"

MAX_INTERPOLATION_DEPTH = 10



# exception classes
class Error(Exception):
    u"""Base class for ConfigParser exceptions."""

    def _get_message(self):
        u"""Getter for 'message'; needed only to override deprecation in
        BaseException.
        """
        return self.__message

    def _set_message(self, value):
        u"""Setter for 'message'; needed only to override deprecation in
        BaseException.
        """
        self.__message = value

    # BaseException.message has been deprecated since Python 2.6.  To prevent
    # DeprecationWarning from popping up over this pre-existing attribute, use
    # a new property that takes lookup precedence.
    message = property(_get_message, _set_message)

    def __init__(self, msg=u''):
        self.message = msg
        Exception.__init__(self, msg)

    def __repr__(self):
        return self.message

    __str__ = __repr__


class NoSectionError(Error):
    u"""Raised when no section matches a requested option."""

    def __init__(self, section):
        Error.__init__(self, u'No section: %r' % (section,))
        self.section = section
        self.args = (section, )


class DuplicateSectionError(Error):
    u"""Raised when a section is repeated in an input source.

    Possible repetitions that raise this exception are: multiple creation
    using the API or in strict parsers when a section is found more than once
    in a single input file, string or dictionary.
    """

    def __init__(self, section, source=None, lineno=None):
        msg = [repr(section), u" already exists"]
        if source is not None:
            message = [u"While reading from ", source]
            if lineno is not None:
                message.append(u" [line {0:2d}]".format(lineno))
            message.append(u": section ")
            message.extend(msg)
            msg = message
        else:
            msg.insert(0, u"Section ")
        Error.__init__(self, u"".join(msg))
        self.section = section
        self.source = source
        self.lineno = lineno
        self.args = (section, source, lineno)


class DuplicateOptionError(Error):
    u"""Raised by strict parsers when an option is repeated in an input source.

    Current implementation raises this exception only when an option is found
    more than once in a single file, string or dictionary.
    """

    def __init__(self, section, option, source=None, lineno=None):
        msg = [repr(option), u" in section ", repr(section),
               u" already exists"]
        if source is not None:
            message = [u"While reading from ", source]
            if lineno is not None:
                message.append(u" [line {0:2d}]".format(lineno))
            message.append(u": option ")
            message.extend(msg)
            msg = message
        else:
            msg.insert(0, u"Option ")
        Error.__init__(self, u"".join(msg))
        self.section = section
        self.option = option
        self.source = source
        self.lineno = lineno
        self.args = (section, option, source, lineno)


class NoOptionError(Error):
    u"""A requested option was not found."""

    def __init__(self, option, section):
        Error.__init__(self, u"No option %r in section: %r" %
                       (option, section))
        self.option = option
        self.section = section
        self.args = (option, section)


class InterpolationError(Error):
    u"""Base class for interpolation-related exceptions."""

    def __init__(self, option, section, msg):
        Error.__init__(self, msg)
        self.option = option
        self.section = section
        self.args = (option, section, msg)


class InterpolationMissingOptionError(InterpolationError):
    u"""A string substitution required a setting which was not available."""

    def __init__(self, option, section, rawval, reference):
        msg = (u"Bad value substitution:\n"
               u"\tsection: [%s]\n"
               u"\toption : %s\n"
               u"\tkey    : %s\n"
               u"\trawval : %s\n"
               % (section, option, reference, rawval))
        InterpolationError.__init__(self, option, section, msg)
        self.reference = reference
        self.args = (option, section, rawval, reference)


class InterpolationSyntaxError(InterpolationError):
    u"""Raised when the source text contains invalid syntax.

    Current implementation raises this exception when the source text into
    which substitutions are made does not conform to the required syntax.
    """


class InterpolationDepthError(InterpolationError):
    u"""Raised when substitutions are nested too deeply."""

    def __init__(self, option, section, rawval):
        msg = (u"Value interpolation too deeply recursive:\n"
               u"\tsection: [%s]\n"
               u"\toption : %s\n"
               u"\trawval : %s\n"
               % (section, option, rawval))
        InterpolationError.__init__(self, option, section, msg)
        self.args = (option, section, rawval)


class ParsingError(Error):
    u"""Raised when a configuration file does not follow legal syntax."""

    def __init__(self, source=None, filename=None):
        # Exactly one of `source'/`filename' arguments has to be given.
        # `filename' kept for compatibility.
        if filename and source:
            raise ValueError(u"Cannot specify both `filename' and `source'. "
                             u"Use `source'.")
        elif not filename and not source:
            raise ValueError(u"Required argument `source' not given.")
        elif filename:
            source = filename
        Error.__init__(self, u'Source contains parsing errors: %s' % source)
        self.source = source
        self.errors = []
        self.args = (source, )

    @property
    def filename(self):
        u"""Deprecated, use `source'."""
        warnings.warn(
            u"The 'filename' attribute will be removed in future versions.  "
            u"Use 'source' instead.",
            DeprecationWarning, stacklevel=2
        )
        return self.source

    @filename.setter
    def filename(self, value):
        u"""Deprecated, user `source'."""
        warnings.warn(
            u"The 'filename' attribute will be removed in future versions.  "
            u"Use 'source' instead.",
            DeprecationWarning, stacklevel=2
        )
        self.source = value

    def append(self, lineno, line):
        self.errors.append((lineno, line))
        self.message += u'\n\t[line %2d]: %s' % (lineno, line)


class MissingSectionHeaderError(ParsingError):
    u"""Raised when a key-value pair is found before any section header."""

    def __init__(self, filename, lineno, line):
        Error.__init__(
            self,
            u'File contains no section headers.\nfile: %s, line: %d\n%r' %
            (filename, lineno, line))
        self.source = filename
        self.lineno = lineno
        self.line = line
        self.args = (filename, lineno, line)


# Used in parser getters to indicate the default behaviour when a specific
# option is not found it to raise an exception. Created to enable `None' as
# a valid fallback value.
_UNSET = object()


class Interpolation(object):
    u"""Dummy interpolation that passes the value through with no changes."""

    def before_get(self, parser, section, option, value, defaults):
        return value

    def before_set(self, parser, section, option, value):
        return value

    def before_read(self, parser, section, option, value):
        return value

    def before_write(self, parser, section, option, value):
        return value


class BasicInterpolation(Interpolation):
    u"""Interpolation as implemented in the classic ConfigParser.

    The option values can contain format strings which refer to other values in
    the same section, or values in the special default section.

    For example:

        something: %(dir)s/whatever

    would resolve the "%(dir)s" to the value of dir.  All reference
    expansions are done late, on demand. If a user needs to use a bare % in
    a configuration file, she can escape it by writing %%. Other other % usage
    is considered a user error and raises `InterpolationSyntaxError'."""

    _KEYCRE = re.compile(ur"%\(([^)]+)\)s")

    def before_get(self, parser, section, option, value, defaults):
        L = []
        self._interpolate_some(parser, option, L, value, section, defaults, 1)
        return u''.join(L)

    def before_set(self, parser, section, option, value):
        tmp_value = value.replace(u'%%', u'') # escaped percent signs
        tmp_value = self._KEYCRE.sub(u'', tmp_value) # valid syntax
        if u'%' in tmp_value:
            raise ValueError(u"invalid interpolation syntax in %r at "
                             u"position %d" % (value, tmp_value.find(u'%')))
        return value

    def _interpolate_some(self, parser, option, accum, rest, section, map,
                          depth):
        if depth > MAX_INTERPOLATION_DEPTH:
            raise InterpolationDepthError(option, section, rest)
        while rest:
            p = rest.find(u"%")
            if p < 0:
                accum.append(rest)
                return
            if p > 0:
                accum.append(rest[:p])
                rest = rest[p:]
            # p is no longer used
            c = rest[1:2]
            if c == u"%":
                accum.append(u"%")
                rest = rest[2:]
            elif c == u"(":
                m = self._KEYCRE.match(rest)
                if m is None:
                    raise InterpolationSyntaxError(option, section,
                        u"bad interpolation variable reference %r" % rest)
                var = parser.optionxform(m.group(1))
                rest = rest[m.end():]
                try:
                    v = map[var]
                except KeyError:
                    raise InterpolationMissingOptionError(
                        option, section, rest, var)
                if u"%" in v:
                    self._interpolate_some(parser, option, accum, v,
                                           section, map, depth + 1)
                else:
                    accum.append(v)
            else:
                raise InterpolationSyntaxError(
                    option, section,
                    u"'%%' must be followed by '%%' or '(', "
                    u"found: %r" % (rest,))


class ExtendedInterpolation(Interpolation):
    u"""Advanced variant of interpolation, supports the syntax used by
    `zc.buildout'. Enables interpolation between sections."""

    _KEYCRE = re.compile(ur"\$\{([^}]+)\}")

    def before_get(self, parser, section, option, value, defaults):
        L = []
        self._interpolate_some(parser, option, L, value, section, defaults, 1)
        return u''.join(L)

    def before_set(self, parser, section, option, value):
        tmp_value = value.replace(u'$$', u'') # escaped dollar signs
        tmp_value = self._KEYCRE.sub(u'', tmp_value) # valid syntax
        if u'$' in tmp_value:
            raise ValueError(u"invalid interpolation syntax in %r at "
                             u"position %d" % (value, tmp_value.find(u'%')))
        return value

    def _interpolate_some(self, parser, option, accum, rest, section, map,
                          depth):
        if depth > MAX_INTERPOLATION_DEPTH:
            raise InterpolationDepthError(option, section, rest)
        while rest:
            p = rest.find(u"$")
            if p < 0:
                accum.append(rest)
                return
            if p > 0:
                accum.append(rest[:p])
                rest = rest[p:]
            # p is no longer used
            c = rest[1:2]
            if c == u"$":
                accum.append(u"$")
                rest = rest[2:]
            elif c == u"{":
                m = self._KEYCRE.match(rest)
                if m is None:
                    raise InterpolationSyntaxError(option, section,
                        u"bad interpolation variable reference %r" % rest)
                path = m.group(1).split(u':')
                rest = rest[m.end():]
                sect = section
                opt = option
                try:
                    if len(path) == 1:
                        opt = parser.optionxform(path[0])
                        v = map[opt]
                    elif len(path) == 2:
                        sect = path[0]
                        opt = parser.optionxform(path[1])
                        v = parser.get(sect, opt, raw=True)
                    else:
                        raise InterpolationSyntaxError(
                            option, section,
                            u"More than one ':' found: %r" % (rest,))
                except (KeyError, NoSectionError, NoOptionError):
                    raise InterpolationMissingOptionError(
                        option, section, rest, u":".join(path))
                if u"$" in v:
                    self._interpolate_some(parser, opt, accum, v, sect,
                                           dict(parser.items(sect, raw=True)),
                                           depth + 1)
                else:
                    accum.append(v)
            else:
                raise InterpolationSyntaxError(
                    option, section,
                    u"'$' must be followed by '$' or '{', "
                    u"found: %r" % (rest,))


class LegacyInterpolation(Interpolation):
    u"""Deprecated interpolation used in old versions of ConfigParser.
    Use BasicInterpolation or ExtendedInterpolation instead."""

    _KEYCRE = re.compile(ur"%\(([^)]*)\)s|.")

    def before_get(self, parser, section, option, value, vars):
        rawval = value
        depth = MAX_INTERPOLATION_DEPTH
        while depth:                    # Loop through this until it's done
            depth -= 1
            if value and u"%(" in value:
                replace = functools.partial(self._interpolation_replace,
                                            parser=parser)
                value = self._KEYCRE.sub(replace, value)
                try:
                    value = value % vars
                except KeyError, e:
                    raise InterpolationMissingOptionError(
                        option, section, rawval, e.args[0])
            else:
                break
        if value and u"%(" in value:
            raise InterpolationDepthError(option, section, rawval)
        return value

    def before_set(self, parser, section, option, value):
        return value

    @staticmethod
    def _interpolation_replace(match, parser):
        s = match.group(1)
        if s is None:
            return match.group()
        else:
            return u"%%(%s)s" % parser.optionxform(s)


class RawConfigParser(MutableMapping):
    u"""ConfigParser that does not do interpolation."""

    # Regular expressions for parsing section headers and options
    _SECT_TMPL = ur"""
        \[                                 # [
        (?P<header>[^]]+)                  # very permissive!
        \]                                 # ]
        """
    _OPT_TMPL = ur"""
        (?P<option>.*?)                    # very permissive!
        \s*(?P<vi>{delim})\s*              # any number of space/tab,
                                           # followed by any of the
                                           # allowed delimiters,
                                           # followed by any space/tab
        (?P<value>.*)$                     # everything up to eol
        """
    _OPT_NV_TMPL = ur"""
        (?P<option>.*?)                    # very permissive!
        \s*(?:                             # any number of space/tab,
        (?P<vi>{delim})\s*                 # optionally followed by
                                           # any of the allowed
                                           # delimiters, followed by any
                                           # space/tab
        (?P<value>.*))?$                   # everything up to eol
        """
    # Interpolation algorithm to be used if the user does not specify another
    _DEFAULT_INTERPOLATION = Interpolation()
    # Compiled regular expression for matching sections
    SECTCRE = re.compile(_SECT_TMPL, re.VERBOSE)
    # Compiled regular expression for matching options with typical separators
    OPTCRE = re.compile(_OPT_TMPL.format(delim=u"=|:"), re.VERBOSE)
    # Compiled regular expression for matching options with optional values
    # delimited using typical separators
    OPTCRE_NV = re.compile(_OPT_NV_TMPL.format(delim=u"=|:"), re.VERBOSE)
    # Compiled regular expression for matching leading whitespace in a line
    NONSPACECRE = re.compile(ur"\S")
    # Possible boolean values in the configuration.
    BOOLEAN_STATES = {u'1': True, u'yes': True, u'true': True, u'on': True,
                      u'0': False, u'no': False, u'false': False, u'off': False}

    def __init__(self, defaults=None, dict_type=_default_dict,
                 allow_no_value=False, **_3to2kwargs):

        if 'interpolation' in _3to2kwargs: interpolation = _3to2kwargs['interpolation']; del _3to2kwargs['interpolation']
        else: interpolation = _UNSET
        if 'default_section' in _3to2kwargs: default_section = _3to2kwargs['default_section']; del _3to2kwargs['default_section']
        else: default_section = DEFAULTSECT
        if 'empty_lines_in_values' in _3to2kwargs: empty_lines_in_values = _3to2kwargs['empty_lines_in_values']; del _3to2kwargs['empty_lines_in_values']
        else: empty_lines_in_values = True
        if 'strict' in _3to2kwargs: strict = _3to2kwargs['strict']; del _3to2kwargs['strict']
        else: strict = True
        if 'inline_comment_prefixes' in _3to2kwargs: inline_comment_prefixes = _3to2kwargs['inline_comment_prefixes']; del _3to2kwargs['inline_comment_prefixes']
        else: inline_comment_prefixes = None
        if 'comment_prefixes' in _3to2kwargs: comment_prefixes = _3to2kwargs['comment_prefixes']; del _3to2kwargs['comment_prefixes']
        else: comment_prefixes = (u'#', u';')
        if 'delimiters' in _3to2kwargs: delimiters = _3to2kwargs['delimiters']; del _3to2kwargs['delimiters']
        else: delimiters = (u'=', u':')
        self._dict = dict_type
        self._sections = self._dict()
        self._defaults = self._dict()
        self._proxies = self._dict()
        self._proxies[default_section] = SectionProxy(self, default_section)
        if defaults:
            for key, value in defaults.items():
                self._defaults[self.optionxform(key)] = value
        self._delimiters = tuple(delimiters)
        if delimiters == (u'=', u':'):
            self._optcre = self.OPTCRE_NV if allow_no_value else self.OPTCRE
        else:
            d = u"|".join(re.escape(d) for d in delimiters)
            if allow_no_value:
                self._optcre = re.compile(self._OPT_NV_TMPL.format(delim=d),
                                          re.VERBOSE)
            else:
                self._optcre = re.compile(self._OPT_TMPL.format(delim=d),
                                          re.VERBOSE)
        self._comment_prefixes = tuple(comment_prefixes or ())
        self._inline_comment_prefixes = tuple(inline_comment_prefixes or ())
        self._strict = strict
        self._allow_no_value = allow_no_value
        self._empty_lines_in_values = empty_lines_in_values
        self.default_section=default_section
        self._interpolation = interpolation
        if self._interpolation is _UNSET:
            self._interpolation = self._DEFAULT_INTERPOLATION
        if self._interpolation is None:
            self._interpolation = Interpolation()

    def defaults(self):
        return self._defaults

    def sections(self):
        u"""Return a list of section names, excluding [DEFAULT]"""
        # self._sections will never have [DEFAULT] in it
        return list(self._sections.keys())

    def add_section(self, section):
        u"""Create a new section in the configuration.

        Raise DuplicateSectionError if a section by the specified name
        already exists. Raise ValueError if name is DEFAULT.
        """
        if section == self.default_section:
            raise ValueError(u'Invalid section name: %r' % section)

        if section in self._sections:
            raise DuplicateSectionError(section)
        self._sections[section] = self._dict()
        self._proxies[section] = SectionProxy(self, section)

    def has_section(self, section):
        u"""Indicate whether the named section is present in the configuration.

        The DEFAULT section is not acknowledged.
        """
        return section in self._sections

    def options(self, section):
        u"""Return a list of option names for the given section name."""
        try:
            opts = self._sections[section].copy()
        except KeyError:
            raise NoSectionError(section)
        opts.update(self._defaults)
        return list(opts.keys())

    def read(self, filenames, encoding=None):
        u"""Read and parse a filename or a list of filenames.

        Files that cannot be opened are silently ignored; this is
        designed so that you can specify a list of potential
        configuration file locations (e.g. current directory, user's
        home directory, systemwide directory), and all existing
        configuration files in the list will be read.  A single
        filename may also be given.

        Return list of successfully read files.
        """
        if isinstance(filenames, unicode) or isinstance(filenames, str):
            filenames = [filenames]
        read_ok = []
        for filename in filenames:
            try:
                with open(filename, encoding=encoding) as fp:
                    self._read(fp, filename)
            except IOError:
                continue
            read_ok.append(filename)
        return read_ok

    def read_file(self, f, source=None):
        u"""Like read() but the argument must be a file-like object.

        The `f' argument must be iterable, returning one line at a time.
        Optional second argument is the `source' specifying the name of the
        file being read. If not given, it is taken from f.name. If `f' has no
        `name' attribute, `<???>' is used.
        """
        if source is None:
            try:
                source = f.name
            except AttributeError:
                source = u'<???>'
        self._read(f, source)

    def read_string(self, string, source=u'<string>'):
        u"""Read configuration from a given string."""
        sfile = io.StringIO(string)
        self.read_file(sfile, source)

    def read_dict(self, dictionary, source=u'<dict>'):
        u"""Read configuration from a dictionary.

        Keys are section names, values are dictionaries with keys and values
        that should be present in the section. If the used dictionary type
        preserves order, sections and their keys will be added in order.

        All types held in the dictionary are converted to strings during
        reading, including section names, option names and keys.

        Optional second argument is the `source' specifying the name of the
        dictionary being read.
        """
        elements_added = set()
        for section, keys in dictionary.items():
            section = unicode(section)
            try:
                self.add_section(section)
            except (DuplicateSectionError, ValueError):
                if self._strict and section in elements_added:
                    raise
            elements_added.add(section)
            for key, value in keys.items():
                key = self.optionxform(unicode(key))
                if value is not None:
                    value = unicode(value)
                if self._strict and (section, key) in elements_added:
                    raise DuplicateOptionError(section, key, source)
                elements_added.add((section, key))
                self.set(section, key, value)

    def readfp(self, fp, filename=None):
        u"""Deprecated, use read_file instead."""
        warnings.warn(
            u"This method will be removed in future versions.  "
            u"Use 'parser.read_file()' instead.",
            DeprecationWarning, stacklevel=2
        )
        self.read_file(fp, source=filename)

    def get(self, section, option, **_3to2kwargs):
        if 'fallback' in _3to2kwargs: fallback = _3to2kwargs['fallback']; del _3to2kwargs['fallback']
        else: fallback = _UNSET
        if 'vars' in _3to2kwargs: vars = _3to2kwargs['vars']; del _3to2kwargs['vars']
        else: vars = None
        if 'raw' in _3to2kwargs: raw = _3to2kwargs['raw']; del _3to2kwargs['raw']
        else: raw = False
        u"""Get an option value for a given section.

        If `vars' is provided, it must be a dictionary. The option is looked up
        in `vars' (if provided), `section', and in `DEFAULTSECT' in that order.
        If the key is not found and `fallback' is provided, it is used as
        a fallback value. `None' can be provided as a `fallback' value.

        If interpolation is enabled and the optional argument `raw' is False,
        all interpolations are expanded in the return values.

        Arguments `raw', `vars', and `fallback' are keyword only.

        The section DEFAULT is special.
        """
        try:
            d = self._unify_values(section, vars)
        except NoSectionError:
            if fallback is _UNSET:
                raise
            else:
                return fallback
        option = self.optionxform(option)
        try:
            value = d[option]
        except KeyError:
            if fallback is _UNSET:
                raise NoOptionError(option, section)
            else:
                return fallback

        if raw or value is None:
            return value
        else:
            return self._interpolation.before_get(self, section, option, value,
                                                  d)

    def _get(self, section, conv, option, **kwargs):
        return conv(self.get(section, option, **kwargs))

    def getint(self, section, option, **_3to2kwargs):
        if 'fallback' in _3to2kwargs: fallback = _3to2kwargs['fallback']; del _3to2kwargs['fallback']
        else: fallback = _UNSET
        if 'vars' in _3to2kwargs: vars = _3to2kwargs['vars']; del _3to2kwargs['vars']
        else: vars = None
        if 'raw' in _3to2kwargs: raw = _3to2kwargs['raw']; del _3to2kwargs['raw']
        else: raw = False
        try:
            return self._get(section, int, option, raw=raw, vars=vars)
        except (NoSectionError, NoOptionError):
            if fallback is _UNSET:
                raise
            else:
                return fallback

    def getfloat(self, section, option, **_3to2kwargs):
        if 'fallback' in _3to2kwargs: fallback = _3to2kwargs['fallback']; del _3to2kwargs['fallback']
        else: fallback = _UNSET
        if 'vars' in _3to2kwargs: vars = _3to2kwargs['vars']; del _3to2kwargs['vars']
        else: vars = None
        if 'raw' in _3to2kwargs: raw = _3to2kwargs['raw']; del _3to2kwargs['raw']
        else: raw = False
        try:
            return self._get(section, float, option, raw=raw, vars=vars)
        except (NoSectionError, NoOptionError):
            if fallback is _UNSET:
                raise
            else:
                return fallback

    def getboolean(self, section, option, **_3to2kwargs):
        if 'fallback' in _3to2kwargs: fallback = _3to2kwargs['fallback']; del _3to2kwargs['fallback']
        else: fallback = _UNSET
        if 'vars' in _3to2kwargs: vars = _3to2kwargs['vars']; del _3to2kwargs['vars']
        else: vars = None
        if 'raw' in _3to2kwargs: raw = _3to2kwargs['raw']; del _3to2kwargs['raw']
        else: raw = False
        try:
            return self._get(section, self._convert_to_boolean, option,
                             raw=raw, vars=vars)
        except (NoSectionError, NoOptionError):
            if fallback is _UNSET:
                raise
            else:
                return fallback

    def items(self, section=_UNSET, raw=False, vars=None):
        u"""Return a list of (name, value) tuples for each option in a section.

        All % interpolations are expanded in the return values, based on the
        defaults passed into the constructor, unless the optional argument
        `raw' is true.  Additional substitutions may be provided using the
        `vars' argument, which must be a dictionary whose contents overrides
        any pre-existing defaults.

        The section DEFAULT is special.
        """
        if section is _UNSET:
            return super(RawConfigParser, self).items()
        d = self._defaults.copy()
        try:
            d.update(self._sections[section])
        except KeyError:
            if section != self.default_section:
                raise NoSectionError(section)
        # Update with the entry specific variables
        if vars:
            for key, value in vars.items():
                d[self.optionxform(key)] = value
        value_getter = lambda option: self._interpolation.before_get(self,
            section, option, d[option], d)
        if raw:
            value_getter = lambda option: d[option]
        return [(option, value_getter(option)) for option in d.keys()]

    def optionxform(self, optionstr):
        return optionstr.lower()

    def has_option(self, section, option):
        u"""Check for the existence of a given option in a given section.
        If the specified `section' is None or an empty string, DEFAULT is
        assumed. If the specified `section' does not exist, returns False."""
        if not section or section == self.default_section:
            option = self.optionxform(option)
            return option in self._defaults
        elif section not in self._sections:
            return False
        else:
            option = self.optionxform(option)
            return (option in self._sections[section]
                    or option in self._defaults)

    def set(self, section, option, value=None):
        u"""Set an option."""
        if value:
            value = self._interpolation.before_set(self, section, option,
                                                   value)
        if not section or section == self.default_section:
            sectdict = self._defaults
        else:
            try:
                sectdict = self._sections[section]
            except KeyError:
                raise NoSectionError(section)
        sectdict[self.optionxform(option)] = value

    def write(self, fp, space_around_delimiters=True):
        u"""Write an .ini-format representation of the configuration state.

        If `space_around_delimiters' is True (the default), delimiters
        between keys and values are surrounded by spaces.
        """
        if space_around_delimiters:
            d = u" {0} ".format(self._delimiters[0])
        else:
            d = self._delimiters[0]
        if self._defaults:
            self._write_section(fp, self.default_section,
                                    self._defaults.items(), d)
        for section in self._sections:
            self._write_section(fp, section,
                                self._sections[section].items(), d)

    def _write_section(self, fp, section_name, section_items, delimiter):
        u"""Write a single section to the specified `fp'."""
        fp.write(u"[{0}]\n".format(section_name))
        for key, value in section_items:
            value = self._interpolation.before_write(self, section_name, key,
                                                     value)
            if value is not None or not self._allow_no_value:
                value = delimiter + unicode(value).replace(u'\n', u'\n\t')
            else:
                value = u""
            fp.write(u"{0}{1}\n".format(key, value))
        fp.write(u"\n")

    def remove_option(self, section, option):
        u"""Remove an option."""
        if not section or section == self.default_section:
            sectdict = self._defaults
        else:
            try:
                sectdict = self._sections[section]
            except KeyError:
                raise NoSectionError(section)
        option = self.optionxform(option)
        existed = option in sectdict
        if existed:
            del sectdict[option]
        return existed

    def remove_section(self, section):
        u"""Remove a file section."""
        existed = section in self._sections
        if existed:
            del self._sections[section]
            del self._proxies[section]
        return existed

    def __getitem__(self, key):
        if key != self.default_section and not self.has_section(key):
            raise KeyError(key)
        return self._proxies[key]

    def __setitem__(self, key, value):
        # To conform with the mapping protocol, overwrites existing values in
        # the section.

        # XXX this is not atomic if read_dict fails at any point. Then again,
        # no update method in configparser is atomic in this implementation.
        self.remove_section(key)
        self.read_dict({key: value})

    def __delitem__(self, key):
        if key == self.default_section:
            raise ValueError(u"Cannot remove the default section.")
        if not self.has_section(key):
            raise KeyError(key)
        self.remove_section(key)

    def __contains__(self, key):
        return key == self.default_section or self.has_section(key)

    def __len__(self):
        return len(self._sections) + 1 # the default section

    def __iter__(self):
        # XXX does it break when underlying container state changed?
        return itertools.chain((self.default_section,), self._sections.keys())

    def _read(self, fp, fpname):
        u"""Parse a sectioned configuration file.

        Each section in a configuration file contains a header, indicated by
        a name in square brackets (`[]'), plus key/value options, indicated by
        `name' and `value' delimited with a specific substring (`=' or `:' by
        default).

        Values can span multiple lines, as long as they are indented deeper
        than the first line of the value. Depending on the parser's mode, blank
        lines may be treated as parts of multiline values or ignored.

        Configuration files may include comments, prefixed by specific
        characters (`#' and `;' by default). Comments may appear on their own
        in an otherwise empty line or may be entered in lines holding values or
        section names.
        """
        elements_added = set()
        cursect = None                        # None, or a dictionary
        sectname = None
        optname = None
        lineno = 0
        indent_level = 0
        e = None                              # None, or an exception
        for lineno, line in enumerate(fp, start=1):
            comment_start = None
            # strip inline comments
            for prefix in self._inline_comment_prefixes:
                index = line.find(prefix)
                if index == 0 or (index > 0 and line[index-1].isspace()):
                    comment_start = index
                    break
            # strip full line comments
            for prefix in self._comment_prefixes:
                if line.strip().startswith(prefix):
                    comment_start = 0
                    break
            value = line[:comment_start].strip()
            if not value:
                if self._empty_lines_in_values:
                    # add empty line to the value, but only if there was no
                    # comment on the line
                    if (comment_start is None and
                        cursect is not None and
                        optname and
                        cursect[optname] is not None):
                        cursect[optname].append(u'') # newlines added at join
                else:
                    # empty line marks end of value
                    indent_level = sys.maxsize
                continue
            # continuation line?
            first_nonspace = self.NONSPACECRE.search(line)
            cur_indent_level = first_nonspace.start() if first_nonspace else 0
            if (cursect is not None and optname and
                cur_indent_level > indent_level):
                cursect[optname].append(value)
            # a section header or option header?
            else:
                indent_level = cur_indent_level
                # is it a section header?
                mo = self.SECTCRE.match(value)
                if mo:
                    sectname = mo.group(u'header')
                    if sectname in self._sections:
                        if self._strict and sectname in elements_added:
                            raise DuplicateSectionError(sectname, fpname,
                                                        lineno)
                        cursect = self._sections[sectname]
                        elements_added.add(sectname)
                    elif sectname == self.default_section:
                        cursect = self._defaults
                    else:
                        cursect = self._dict()
                        self._sections[sectname] = cursect
                        self._proxies[sectname] = SectionProxy(self, sectname)
                        elements_added.add(sectname)
                    # So sections can't start with a continuation line
                    optname = None
                # no section header in the file?
                elif cursect is None:
                    raise MissingSectionHeaderError(fpname, lineno, line)
                # an option line?
                else:
                    mo = self._optcre.match(value)
                    if mo:
                        optname, vi, optval = mo.group(u'option', u'vi', u'value')
                        if not optname:
                            e = self._handle_error(e, fpname, lineno, line)
                        optname = self.optionxform(optname.rstrip())
                        if (self._strict and
                            (sectname, optname) in elements_added):
                            raise DuplicateOptionError(sectname, optname,
                                                       fpname, lineno)
                        elements_added.add((sectname, optname))
                        # This check is fine because the OPTCRE cannot
                        # match if it would set optval to None
                        if optval is not None:
                            optval = optval.strip()
                            cursect[optname] = [optval]
                        else:
                            # valueless option handling
                            cursect[optname] = None
                    else:
                        # a non-fatal parsing error occurred. set up the
                        # exception but keep going. the exception will be
                        # raised at the end of the file and will contain a
                        # list of all bogus lines
                        e = self._handle_error(e, fpname, lineno, line)
        # if any parsing errors occurred, raise an exception
        if e:
            raise e
        self._join_multiline_values()

    def _join_multiline_values(self):
        defaults = self.default_section, self._defaults
        all_sections = itertools.chain((defaults,),
                                       self._sections.items())
        for section, options in all_sections:
            for name, val in options.items():
                if isinstance(val, list):
                    val = u'\n'.join(val).rstrip()
                options[name] = self._interpolation.before_read(self,
                                                                section,
                                                                name, val)

    def _handle_error(self, exc, fpname, lineno, line):
        if not exc:
            exc = ParsingError(fpname)
        exc.append(lineno, repr(line))
        return exc

    def _unify_values(self, section, vars):
        u"""Create a sequence of lookups with 'vars' taking priority over
        the 'section' which takes priority over the DEFAULTSECT.

        """
        sectiondict = {}
        try:
            sectiondict = self._sections[section]
        except KeyError:
            if section != self.default_section:
                raise NoSectionError(section)
        # Update with the entry specific variables
        vardict = {}
        if vars:
            for key, value in vars.items():
                if value is not None:
                    value = unicode(value)
                vardict[self.optionxform(key)] = value
        return _ChainMap(vardict, sectiondict, self._defaults)

    def _convert_to_boolean(self, value):
        u"""Return a boolean value translating from other types if necessary.
        """
        if value.lower() not in self.BOOLEAN_STATES:
            raise ValueError(u'Not a boolean: %s' % value)
        return self.BOOLEAN_STATES[value.lower()]

    def _validate_value_types(self, **_3to2kwargs):
        if 'value' in _3to2kwargs: value = _3to2kwargs['value']; del _3to2kwargs['value']
        else: value = u""
        if 'option' in _3to2kwargs: option = _3to2kwargs['option']; del _3to2kwargs['option']
        else: option = u""
        if 'section' in _3to2kwargs: section = _3to2kwargs['section']; del _3to2kwargs['section']
        else: section = u""
        u"""Raises a TypeError for non-string values.

        The only legal non-string value if we allow valueless
        options is None, so we need to check if the value is a
        string if:
        - we do not allow valueless options, or
        - we allow valueless options but the value is not None

        For compatibility reasons this method is not used in classic set()
        for RawConfigParsers. It is invoked in every case for mapping protocol
        access and in ConfigParser.set().
        """
        if not isinstance(section, basestring):
            raise TypeError(u"section names must be strings")
        if not isinstance(option, basestring):
            raise TypeError(u"option keys must be strings")
        if not self._allow_no_value or value:
            if not isinstance(value, basestring):
                raise TypeError(u"option values must be strings")
        return (unicode(section), unicode(option), (value if value is None
            else unicode(value)))


class ConfigParser(RawConfigParser):
    u"""ConfigParser implementing interpolation."""

    _DEFAULT_INTERPOLATION = BasicInterpolation()

    def set(self, section, option, value=None):
        u"""Set an option.  Extends RawConfigParser.set by validating type and
        interpolation syntax on the value."""
        _, option, value = self._validate_value_types(option=option, value=value)
        super(ConfigParser, self).set(section, option, value)

    def add_section(self, section):
        u"""Create a new section in the configuration.  Extends
        RawConfigParser.add_section by validating if the section name is
        a string."""
        section, _, _ = self._validate_value_types(section=section)
        super(ConfigParser, self).add_section(section)


class SafeConfigParser(ConfigParser):
    u"""ConfigParser alias for backwards compatibility purposes."""

    def __init__(self, *args, **kwargs):
        super(SafeConfigParser, self).__init__(*args, **kwargs)
        warnings.warn(
            u"The SafeConfigParser class has been renamed to ConfigParser "
            u"in Python 3.2. This alias will be removed in future versions."
            u" Use ConfigParser directly instead.",
            DeprecationWarning, stacklevel=2
        )


class SectionProxy(MutableMapping):
    u"""A proxy for a single section from a parser."""

    def __init__(self, parser, name):
        u"""Creates a view on a section of the specified `name` in `parser`."""
        self._parser = parser
        self._name = name

    def __repr__(self):
        return u'<Section: {0}>'.format(self._name)

    def __getitem__(self, key):
        if not self._parser.has_option(self._name, key):
            raise KeyError(key)
        return self._parser.get(self._name, key)

    def __setitem__(self, key, value):
        _, key, value = self._parser._validate_value_types(option=key, value=value)
        return self._parser.set(self._name, key, value)

    def __delitem__(self, key):
        if not (self._parser.has_option(self._name, key) and
                self._parser.remove_option(self._name, key)):
            raise KeyError(key)

    def __contains__(self, key):
        return self._parser.has_option(self._name, key)

    def __len__(self):
        return len(self._options())

    def __iter__(self):
        return self._options().__iter__()

    def _options(self):
        if self._name != self._parser.default_section:
            return self._parser.options(self._name)
        else:
            return self._parser.defaults()

    def get(self, option, fallback=None, **_3to2kwargs):
        if 'vars' in _3to2kwargs: vars = _3to2kwargs['vars']; del _3to2kwargs['vars']
        else: vars = None
        if 'raw' in _3to2kwargs: raw = _3to2kwargs['raw']; del _3to2kwargs['raw']
        else: raw = False
        return self._parser.get(self._name, option, raw=raw, vars=vars,
                                fallback=fallback)

    def getint(self, option, fallback=None, **_3to2kwargs):
        if 'vars' in _3to2kwargs: vars = _3to2kwargs['vars']; del _3to2kwargs['vars']
        else: vars = None
        if 'raw' in _3to2kwargs: raw = _3to2kwargs['raw']; del _3to2kwargs['raw']
        else: raw = False
        return self._parser.getint(self._name, option, raw=raw, vars=vars,
                                   fallback=fallback)

    def getfloat(self, option, fallback=None, **_3to2kwargs):
        if 'vars' in _3to2kwargs: vars = _3to2kwargs['vars']; del _3to2kwargs['vars']
        else: vars = None
        if 'raw' in _3to2kwargs: raw = _3to2kwargs['raw']; del _3to2kwargs['raw']
        else: raw = False
        return self._parser.getfloat(self._name, option, raw=raw, vars=vars,
                                     fallback=fallback)

    def getboolean(self, option, fallback=None, **_3to2kwargs):
        if 'vars' in _3to2kwargs: vars = _3to2kwargs['vars']; del _3to2kwargs['vars']
        else: vars = None
        if 'raw' in _3to2kwargs: raw = _3to2kwargs['raw']; del _3to2kwargs['raw']
        else: raw = False
        return self._parser.getboolean(self._name, option, raw=raw, vars=vars,
                                       fallback=fallback)

    @property
    def parser(self):
        # The parser object of the proxy is read-only.
        return self._parser

    @property
    def name(self):
        # The name of the section on a proxy is read-only.
        return self._name
