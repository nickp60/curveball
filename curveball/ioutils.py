#!/usr/bin/env python
# -*- coding: utf-8 -*-

# This file is part of curveball.
# https://github.com/yoavram/curveball

# Licensed under the MIT license:
# http://www.opensource.org/licenses/MIT-license
# Copyright (c) 2015, Yoav Ram <yoavram+github@gmail.com>
import xlrd
import pandas as pd
from string import ascii_uppercase


MAT_VERSION = '1.0'


def read_tecan_xlsx(filename, label, sheet=None, max_time=None, plate=None):
    """Reads growth measurements from a Tecan Infinity Excel output file.

    Args:
        filename: Path to the file (:py:class:`str`).
        label: String or sequence of strings of measurment names used as titles of the data tables in the file.
        sheet: Sheet number, if known. Otherwise the function will try to guess the sheet.
        max_time: The maximal time, in hours (:py:class:`int`).
        plate: A pandas DataFrame object representing a plate, usually generated by reading a CSV file generated by `Plato <http://plato.yoavram.com/>`_.

    Returns:
        A :py:class:`pandasDataFrame` containing the columns:

        - `Time` (:py:class:`int`, in hours)
        - `Temp. [°C]` (:py:class:`float`)
        - `Cycle Nr.` (:py:class:`int`)
        - `Well` (:py:class:`str`): the well name, usually a letter for the row and a number of the column.
        - `Row` (:py:class:`str`): the letter corresponding to the well row.
        - `Col` (:py:class:`str`): the number corresponding to the well column.
        - `Strain` (:py:class:`str`): if a `plate` was given, this is the strain name corresponding to the well from the plate.
        - `Color` (:py:class:`str`, hex format): if a `plate` was given, this is the strain color corresponding to the well from the plate.

        There will also be a separate column for each label, and if there is more than one label, a separate `Time` and `Temp. [°C]` column for each label.

    Example:

    >>> plate = pd.read_csv("plate_templates/G-RG-R.csv")
    >>> df = curveball.io.read_tecan_xlsx("data/yoavram/210115.xlsx", ('OD','Green','Red'), max_time=12, plate=plate)
    >>> df.columns
    Index([u'Time_OD', u'Temp. [°C]_OD', u'Cycle Nr.', u'Well', u'OD', u'Row', u'Col', u'Strain', u'Color', u'Time_Green', u'Temp. [°C]_Green', u'Green', u'Time', u'Temp. [°C]', u'Red'], dtype='object')
    """
    wb = xlrd.open_workbook(filename)
    if sheet == None:
        for sh in wb.sheets():
            if sh.nrows > 0:
                break
    else:
        sh = wb.sheets()[sheet]

    if isinstance(label, str):
        label = [label]

    dataframes = []
    for lbl in label:
        for i in range(sh.nrows):
            row = sh.row_values(i)
            if row[0] == lbl:
                break

        data = {}
        for i in range(i+1, sh.nrows):
            row = sh.row(i)
            if row[0].value == '':
                break
            data[row[0].value] = [x.value for x in row[1:] if x.ctype == 2]

        min_length = min(map(len, data.values()))
        for k,v in data.items():
            data[k] =  v[:min_length]

        df = pd.DataFrame(data)
        df = pd.melt(df, id_vars=('Time [s]',u'Temp. [°C]','Cycle Nr.'), var_name='Well', value_name=lbl)
        df.rename(columns={'Time [s]': 'Time'}, inplace=True)
        df.Time = df.Time / 3600.
        df['Row'] = map(lambda x: x[0], df.Well)
        df['Col'] = map(lambda x: int(x[1:]), df.Well)
        if plate is None:
            df['Strain'] = 0
            df['Color'] = '#000000'
        else:
            df = pd.merge(df, plate, on=('Row','Col'))
        if not max_time:
            max_time = df.Time.max()
        df = df[df.Time < max_time]
        dataframes.append((lbl,df))

    if len(dataframes) == 0:
        return pd.DataFrame()
    if len(dataframes) == 1:
        return dataframes[0][1]
    else:
        # FIXME last label isn't used as a suffix, not sure why
        lbl,df = dataframes[0]
        lbl = '_' + lbl
        for lbli,dfi in dataframes[1:]:
            lbli = '_' + lbli
            df = pd.merge(df, dfi, on=('Cycle Nr.','Well','Row','Col','Strain','Color'), suffixes=(lbl,lbli))
        return df


    def read_tecan_mat(filename, time_label='tps', value_label='plate_mat', value_name='OD', plate_width=12, max_time=None, plate=None):
        """Reads growth measurements from a Tecan mat file.
        """
        mat = loadmat(filename, appendmat=True)
        if mat['__version__'] != MAT_VERSION:
            print "Warning: expected mat file version %s but got %s" % (MAT_VERSION, mat['__version__'])
        t = mat[time_label].
        t = t.reshape(max(t.shape))
        y = mat[value_label]
        assert y.shape[1] == t.shape[0]

        df = pd.DataFrame(y.T, columns=np.arange(y.shape[0]) + 1)
        df['Time'] = t / 3600.
        df['Cycle Nr.'] = np.arange(1, 1 + len(t))
        df = pd.melt(df, id_vars=('Cycle Nr.', 'Time'), var_name='Well', value_name=value_name)
        df['Well'] = map(lambda w: ascii_uppercase[(int(w)-1)/plate_width] + str(w%plate_width if w%plate_width > 0 else plate_width), df['Well'])
        df['Row'] = map(lambda w: w[0], df['Well'])
        df['Col'] = map(lambda w: int(w[1:]), df['Well'])
        
        if plate is None:
            df['Strain'] = 0
            df['Color'] = '#000000'
        else:
            df = pd.merge(df, plate, on=('Row','Col'))
        if not max_time:
            max_time = df.Time.max()
        df = df[df.Time < max_time]       
        return df


    