#!/usr/bin/env python
# -*- coding: utf-8 -*-

# This file is part of curveball.
# https://github.com/yoavram/curveball

# Licensed under the MIT license:
# http://www.opensource.org/licenses/MIT-license
# Copyright (c) 2015, Yoav Ram <yoav@yoavram.com>
from __future__ import print_function
from __future__ import division
from builtins import zip
from builtins import str
from builtins import filter
from builtins import map
from builtins import range
from six import string_types
from past.utils import old_div
import xlrd
import numpy as np
import pandas as pd
from string import ascii_uppercase
from scipy.io import loadmat
from lxml import etree
import re
import datetime
import dateutil.parser
from glob import glob
import os.path
from warnings import warn


MAT_VERSION = u'1.0'


def read_tecan_xlsx(filename, label=u'OD', sheet=None, max_time=None, plate=None):
    """Reads growth measurements from a Tecan Infinity Excel output file.

    Parameters
    ----------
    filename : str
        path to the file.
    label : str / sequence of str
        a string or sequence of strings containing measurment names used as titles of the data tables in the file.
    sheet : int, optional
        sheet number, if known. Otherwise the function will try to guess the sheet.
    max_time : float, optional
        maximal time in hours, defaults to infinity
    plate : pandas.DataFrame, optional
        data frame representing a plate, usually generated by reading a CSV file generated by `Plato <http://plato.yoavram.com/>`_.

    Returns
    -------
    pandas.DataFrame
        Data frame containing the columns:

        - ``Time`` (:py:class:`float`, in hours)
        - ``Temp. [°C]`` (:py:class:`float`)
        - ``Cycle Nr.`` (:py:class:`int`)
        - ``Well`` (:py:class:`str`): the well name, usually a letter for the row and a number of the column.
        - ``Row`` (:py:class:`str`): the letter corresponding to the well row.
        - ``Col`` (:py:class:`str`): the number corresponding to the well column.
        - ``Strain`` (:py:class:`str`): if a `plate` was given, this is the strain name corresponding to the well from the plate.
        - ``Color`` (:py:class:`str`, hex format): if a `plate` was given, this is the strain color corresponding to the well from the plate.

        There will also be a separate column for each label, and if there is more than one label, a separate `Time` and `Temp. [°C]` column for each label.

    Raises
    ------
    ValueError
        if not data was parsed from the file.

    Example
    -------
    
    >>> plate = pd.read_csv("plate_templates/G-RG-R.csv")
    >>> df = curveball.ioutils.read_tecan_xlsx("data/Tecan_210115.xlsx", label=('OD','Green','Red'), max_time=12, plate=plate)
    >>> df.shape
    (8544, 9)
    """
    wb = xlrd.open_workbook(filename)
    dateandtime = datetime.datetime.now() # default

    if isinstance(label, string_types):
        label = [label]
    
    label_dataframes = []
    for lbl in label:
        sheet_dataframes = []
        for sh in wb.sheets():
            if sh.nrows == 0:
                continue # to next sheet
        ## FOR sheet
            for i in range(sh.nrows):
                ## FOR row
                row = sh.row_values(i)                
                if row[0].startswith(u'Date'):
                    if isinstance(row[1], string_types):
                        date = ''.join(row[1:])
                        next_row = sh.row_values(i + 1)
                        if next_row[0].startswith(u'Time'):
                            time = ''.join(next_row[1:])
                        else:
                            warn(u"Warning: time row missing (sheet '{0}', row{1}), found row starting with {2}".format(sh.name, i, row[0]))
                        dateandtime = dateutil.parser.parse("%s %s" % (date, time))
                    elif isinstance(row[1], float):
                        date_tuple = xlrd.xldate_as_tuple(row[1], wb.datemode)
                        next_row = sh.row_values(i + 1)
                        if next_row[0].startswith(u'Time'):
                            time = tuple(map(int, next_row[1].split(':')))[:3]
                            date_tuple = date_tuple[:3] + time
                        else:
                            warn(u"Warning: time row missing (sheet '{0}', row{1}), found row starting with {2}".format(sh.name, i, row[0]))
                        dateandtime = datetime.datetime(*date_tuple)
                    else:
                        warn(u"Warning: date row (sheet '{2}', row {3}) could not be parsed: {0} {1}".format(row[1], type(row[1]), sh.name, i))
                if row[0] == lbl:
                    break
                ## FOR row ENDS
            
            data = {}            
            for j in range(i + 1, sh.nrows):
                ## FOR row
                row = sh.row(j)
                if len(row[0].value) == 0:
                    break
                data[row[0].value] = [x.value for x in row[1:] if x.ctype == 2]
                ## FOR row ENDS

            if len(data) == 0:
                raise ValueError("No data found in file {0}".format(filename))

            min_length = min(map(len, data.values()))
            for k,v in data.items():
                data[k] =  v[:min_length]

            df = pd.DataFrame(data)
            df = pd.melt(df, id_vars=(u'Time [s]', u'Temp. [°C]', u'Cycle Nr.'), var_name=u'Well', value_name=lbl)
            df.rename(columns={u'Time [s]': u'Time'}, inplace=True)
            df.Time = [dateandtime + datetime.timedelta(0, t) for t in df.Time]        
            df[u'Row'] = [x[0] for x in df.Well]
            df[u'Col'] = [int(x[1:]) for x in df.Well]
            sheet_dataframes.append(df)
        ## FOR sheet ENDS

        if len(sheet_dataframes) == 0:
            df = pd.DataFrame()
        elif len(sheet_dataframes) == 1:
            df = sheet_dataframes[0]
        else:
            df = pd.concat(sheet_dataframes)

        min_time = df.Time.min()
        df.Time = [old_div((t - min_time).total_seconds(), 3600.) for t in df.Time]
        if not max_time is None:
            df = df[df.Time <= max_time]
        df.sort([u'Row', u'Col', u'Time'], inplace=True)
        label_dataframes.append((lbl,df))

    if len(label_dataframes) == 0: # dataframes
        return pd.DataFrame()
    if len(label_dataframes) == 1: # just one dataframe
        df = label_dataframes[0][1]
    else: # multiple dataframes, merge together
        # FIXME last label isn't used as a suffix, not sure why
        lbl, df = label_dataframes[0]
        lbl = '_' + lbl
        for lbli, dfi in label_dataframes[1:]:
            lbli = '_' + lbli
            df = pd.merge(df, dfi, on=(u'Cycle Nr.', u'Well', u'Row', u'Col'), suffixes=(lbl,lbli))
    if plate is None:
        df[u'Strain'] = 0
        df[u'Color'] = u'#000000'
    else:
        df = pd.merge(df, plate, on=(u'Row', u'Col'))
    return df


def read_tecan_mat(filename, time_label=u'tps', value_label=u'plate_mat', value_name=u'OD', plate_width=12, max_time=None, plate=None):
    """Reads growth measurements from a Matlab file generated by a propriety script at the *Pilpel lab*.

    Parameters
    ----------
    filename : str
        name of the XML file to be read. Use ``*`` and ``?`` in filename to read multiple files and parse them into a single data frame.
    time_label : str, optional
        name of the field used to store the time values, defaults to ``tps``.
    label : str
        name of the field used to store the OD values, defaults to ``plate_mat``.
    plate_width : int
        width of the microwell in plate in number of wells, defaults to 12.
    max_time : float, optional
        maximal time in hours, defaults to infinity
    plate : pandas.DataFrame, optional
        data frame representing a plate, usually generated by reading a CSV file generated by `Plato <http://plato.yoavram.com/>`_.

    Returns
    -------
    pandas.DataFrame
        Data frame containing the columns:

        - ``Time`` (:py:class:`float`, in hours)
        - ``OD`` (:py:class:`float`)
        - ``Well`` (:py:class:`str`): the well name, usually a letter for the row and a number of the column.
        - ``Row`` (:py:class:`str`): the letter corresponding to the well row.
        - ``Col`` (:py:class:`str`): the number corresponding to the well column.
        - ``Filename`` (:py:class:`str`): the filename from which this measurement was read.
        - ``Strain`` (:py:class:`str`): if a `plate` was given, this is the strain name corresponding to the well from the plate.
        - ``Color`` (:py:class:`str`, hex format): if a `plate` was given, this is the strain color corresponding to the well from the plate.
    """
    mat = loadmat(filename, appendmat=True)
    if mat[u'__version__'] != MAT_VERSION:
        warn(u"Warning: expected mat file version {0} but got {1}".format(MAT_VERSION, mat[u'__version__']))
    t = mat[time_label]
    t = t.reshape(max(t.shape))
    y = mat[value_label]
    assert y.shape[1] == t.shape[0]

    df = pd.DataFrame(y.T, columns=np.arange(y.shape[0]) + 1)
    df[u'Time'] = old_div(t, 3600.)
    df[u'Cycle Nr.'] = np.arange(1, 1 + len(t))
    df = pd.melt(df, id_vars=(u'Cycle Nr.', u'Time'), var_name=u'Well', value_name=value_name)
    df[u'Well'] = [ascii_uppercase[old_div((int(w) - 1), plate_width)] + str(w % plate_width if w % plate_width > 0 else plate_width) for w in df[u'Well']]
    df[u'Row'] = [w[0] for w in df[u'Well']]
    df[u'Col'] = [int(w[1:]) for w in df[u'Well']]
    
    if plate is None:
        df[u'Strain'] = 0
        df[u'Color'] = u'#000000'
    else:
        df = pd.merge(df, plate, on=(u'Row', u'Col'))
    if not max_time:
        max_time = df.Time.max()
    df = df[df.Time < max_time]
    df.sort([u'Row', u'Col', u'Time'], inplace=True)    
    return df


def read_tecan_xml(filename, label=u'OD', max_time=None, plate=None):
    """Reads growth measurements from a Tecan Infinity XML output files.

    Parameters
    ----------
    filename : str
        pattern of the XML files to be read. Use ``*`` and ``?`` in filename to read multiple files and parse them into a single data frame.
    label : str, optional
        measurment name used as ``Name`` in the measurement sections in the file, defaults to ``OD``.
    max_time : float, optional
        maximal time in hours, defaults to infinity
    plate : pandas.DataFrame, optional
        data frame representing a plate, usually generated by reading a CSV file generated by `Plato <http://plato.yoavram.com/>`_.

    Returns
    -------
    pandas.DataFrame
        Data frame containing the columns:

        - ``Time`` (:py:class:`float`, in hours)
        - ``Well`` (:py:class:`str`): the well name, usually a letter for the row and a number of the column.
        - ``Row`` (:py:class:`str`): the letter corresponding to the well row.
        - ``Col`` (:py:class:`str`): the number corresponding to the well column.
        - ``Filename`` (:py:class:`str`): the filename from which this measurement was read.
        - ``Strain`` (:py:class:`str`): if a `plate` was given, this is the strain name corresponding to the well from the plate.
        - ``Color`` (:py:class:`str`, hex format): if a `plate` was given, this is the strain color corresponding to the well from the plate.

    There will also be a separate column for the value of the label.

    Example
    -------    

    >>> import zipfile
    >>> with zipfile.ZipFile("data/20130211_dh.zip") as z:
        z.extractall("data/20130211_dh")
    >>> plate = pd.read_csv("plate_templates/checkerboard.csv")
    >>> df = curveball.ioutils.read_tecan_xlsx("data/20130211_dh/*.xml", 'OD', plate=plate)
    >>> df.shape
    (2016, 8)

    Notes
    -----
    This function was adapted from `choderalab/assaytools <https://github.com/choderalab/assaytools/blob/908471e7976e207df3f9b0e31b2a89f84da40607/AssayTools/platereader.py>`_ (licensed under LGPL).
    """
    dataframes = []
    for filename in glob(filename):
        # Parse XML file into nodes.
        root_node = etree.parse(filename)

        # Build a dict of section nodes.
        section_nodes = { section_node.get(u'Name') : section_node for section_node in root_node.xpath(u"/*/Section") }

        # Process all sections.
        if label not in section_nodes:
            return pd.DataFrame()

        section_node = section_nodes[label]
        
        # Get the time of measurement
        time_start = section_node.attrib[u'Time_Start']

        # Get a list of all well nodes
        well_nodes = section_node.xpath(u"*/Well")
        
        # Process all wells into data.
        well_data = []
        for well_node in well_nodes:
            well = well_node.get(u'Pos')
            value = float(well_node.xpath(u"string()"))
            well_data.append({u'Well': well, label: value})

        # Add to data frame
        df = pd.DataFrame(well_data)
        df[u'Row'] = [x[0] for x in df.Well]
        df[u'Col'] = [int(x[1:]) for x in df.Well]
        df[u'Time'] = dateutil.parser.parse(time_start)
        df[u'Filename'] = os.path.split(filename)[-1]
        dataframes.append(df)
    df = pd.concat(dataframes)
    min_time = df.Time.min()
    df.Time = [old_div((t - min_time).total_seconds(), 3600.) for t in df.Time]
    if plate is None:
        df[u'Strain'] = 0
        df[u'Color'] = u'#000000'
    else:
        df = pd.merge(df, plate, on=(u'Row', u'Col'))
    if not max_time is None:
        df = df[df.Time <= max_time]
    df.sort([u'Row', u'Col', u'Time'], inplace=True)
    return df


def read_sunrise_xlsx(filename, label=u'OD', max_time=None, plate=None):
    """Reads growth measurements from a Tecan Sunrise Excel output file.

    Parameters
    ----------
    filename : str
        pattern of the XLSX files to be read. Use * and ? in filename to read multiple files and parse them into a single data frame.    label : str, optional
    label : str, optional
        measurment name to use for the data in the file, defaults to ``OD``.
    max_time : float, optional
        maximal time in hours, defaults to infinity
    plate : pandas.DataFrame, optional
        data frame representing a plate, usually generated by reading a CSV file generated by `Plato <http://plato.yoavram.com/>`_.

    Returns
    -------
    pandas.DataFrame
        Data frame containing the columns:

        - ``Time`` (:py:class:`float`, in hours)
        - ``OD`` (or the value of `label`, if given)
        - ``Well`` (:py:class:`str`): the well name, usually a letter for the row and a number of the column.
        - ``Row`` (:py:class:`str`): the letter corresponding to the well row.
        - ``Col`` (:py:class:`str`): the number corresponding to the well column.
        - ``Filename`` (:py:class:`str`): the filename from which this measurement was read.
        - ``Strain`` (:py:class:`str`): if a `plate` was given, this is the strain name corresponding to the well from the plate.
        - ``Color`` (:py:class:`str`, hex format): if a `plate` was given, this is the strain color corresponding to the well from the plate.
    """
    dataframes = []
    files = glob(filename)
    if not files:
        return pd.DataFrame()
    for filename in files:
        wb = xlrd.open_workbook(filename)
        for sh in wb.sheets():
            if sh.nrows > 0:
                break
        parse_data = False # start with metadata
        index = []
        data = []

        for i in range(sh.nrows):
            row = sh.row_values(i)
            if row[0] == u'Date:':
                date = next(filter(lambda x: isinstance(x, float), row[1:]))
                date = xlrd.xldate_as_tuple(date, 0)        
            elif row[0] == u'Time:':
                time = next(filter(lambda x: isinstance(x, float), row[1:]))
                time = xlrd.xldate_as_tuple(time, 0)
            elif row[0] == u'<>':
                columns = list(map(int, row[1:]))
                parse_data = True
            elif len(row[0]) == 0 and parse_data:
                break
            elif parse_data:
                index.append(row[0])
                data.append(list(map(float, row[1:])))
                
        dateandtime = date[:3] + time[-3:]
        dateandtime = datetime.datetime(*dateandtime)
        
        df = pd.DataFrame(data, columns=columns, index=index)
        df[u'Row'] = index
        df = pd.melt(df, id_vars=u'Row', var_name=u'Col', value_name=label)
        df[u'Time'] = dateandtime
        df[u'Well'] = [x[0] + str(x[1]) for x in zip(df.Row, df.Col)]
        df[u'Filename'] = os.path.split(filename)[-1]
        dataframes.append(df)
    df = pd.concat(dataframes)
    min_time = df.Time.min()
    df.Time = [old_div((t - min_time).total_seconds(), 3600.) for t in df.Time]
    if plate is None:
        df[u'Strain'] = 0
        df[u'Color'] = u'#000000'
    else:
        df = pd.merge(df, plate, on=(u'Row', u'Col'))
    if not max_time is None:
        df = df[df.Time <= max_time]
    df.sort([u'Row', u'Col', u'Time'], inplace=True)
    return df