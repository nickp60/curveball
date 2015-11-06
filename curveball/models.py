#!/usr/bin/env python
# -*- coding: utf-8 -*-

# This file is part of curveball.
# https://github.com/yoavram/curveball

# Licensed under the MIT license:
# http://www.opensource.org/licenses/MIT-license
# Copyright (c) 2015, Yoav Ram <yoav@yoavram.com>
from __future__ import print_function
from __future__ import division
from builtins import filter
from builtins import str
from builtins import range
from past.utils import old_div
import sys
from warnings import warn
import numpy as np
import matplotlib.pyplot as plt
import collections
from scipy.stats import chisqprob
from scipy.misc import derivative
import pandas as pd
import copy
from lmfit import Model
from lmfit.models import LinearModel
from curveball.baranyi_roberts_model import baranyi_roberts_function, BaranyiRobertsModel
import sympy
import seaborn as sns
sns.set_style("ticks")


def sample_params(model_fit, nsamples, params=None, covar=None):
    """Random sample of parameter values from a truncated multivariate normal distribution defined by the 
    covariance matrix of the a model fitting result.

    Parameters
    ----------
    model_fit : lmfit.model.ModelResult
        the model fit that defines the sampled distribution
    nsamples : int
        number of samples to make
    params: dict, optional
        a dictionary of model parameter values; if given, overrides values from `model_fit`
    covar: numpy.ndarray, optional
        an array containing the parameters covariance matrix; if given, overrides values from `model_fit`
    

    Returns
    -------
    pandas.DataFrame
        data frame of samples; each row is a sample, each column is a parameter.
    """        
    if params is None:
        params = model_fit.params
    else:
        _params = copy.copy(model_fit.params)
        for pname, pvalue in params.items():
            _params[pname].value = pvalue
        params = _params
    if covar is None:
        covar = model_fit.covar
    if covar.ndim != 2:
        warn("Covariance matrix doesn't have 2 dimensions: \n{}".format(covar))
    w, h = covar.shape
    if w != h:
        warn("Covariance matrix is not square: \n{}".format(covar))
    names = [p.name for p in params.values() if p.vary]
    means = [p.value for p in params.values() if p.vary]
        
    param_samples = np.random.multivariate_normal(means, covar, nsamples)
    param_samples = pd.DataFrame(param_samples, columns=names)
    idx = np.zeros(nsamples) == 0
    for p in params.values():
        if not p.vary:
            continue
        idx = idx & (param_samples[p.name] >= p.min) & (param_samples[p.name] <= p.max)
    if param_samples.shape[0] < nsamples:
        warn("Warning: truncated {0} parameter samples; please report at {1}, including the data and use case.".format(nsamples - param_samples.shape[0], "https://github.com/yoavram/curveball/issues"))
    return param_samples[idx]
    

def lrtest(m0, m1, alfa=0.05):
    r"""Performs a likelihood ratio test on two nested models.

    For two models, one nested in the other (meaning that the nested model estimated parameters are a subset of the nesting model), the test statistic :math:`D` is:

    .. math::

        \Lambda = \Big( \Big(\frac{\sum{(X_i - \hat{X_i}(\theta_1))^2}}{\sum{(X_i - \hat{X_i}(\theta_0))^2}}\Big)^{n/2} \Big)

        D = -2 log \Lambda

        lim_{n \to \infty} D \sim \chi^2_{df=\Delta}


    where :math:`\Lambda` is the likelihood ratio, :math:`D` is the statistic, 
    :math:`X_{i}` are the data points, :math:`\hat{X_i}(\theta)` is the model prediction with parameters :math:`\theta`, 
    :math:`\theta_i` is the parameters estimation for model :math:`i`, 
    :math:`n` is the number of data points, and :math:`\Delta` is the difference in number of parameters between the models.

    The function compares between two :py:class:`lmfit.model.ModelResult` objects. 
    These are the results of fitting models to the same data set using the `lmfit <lmfit.github.io/lmfit-py>`_ package

    The function compares between model fit `m0` and `m1` and assumes that `m0` is nested in `m1`, 
    meaning that the set of varying parameters of `m0` is a subset of the varying parameters of `m1`. 
    The property ``chisqr`` of the :py:class:`lmfit.model.ModelResult` objects is 
    the sum of the square of the residuals of the fit. 
    ``ndata`` is the number of data points. 
    ``nvarys`` is the number of varying parameters.

    Parameters
    ----------
    m0, m1 : lmfit.model.ModelResult
        objects representing two model fitting results. `m0` is assumed to be nested in `m1`.
    alfa : float, optional
        test significance level, defaults to 0.05 = 5%.

    Returns
    -------
    prefer_m1 : bool
        should we prefer `m1` over `m0`
    pval : float
        the test p-value
    D : float
        the test statistic
    ddf : int 
        the number of degrees of freedom

    See also
    --------
    `Generalised Likelihood Ratio Test Example <http://www.stat.sc.edu/~habing/courses/703/GLRTExample.pdf>`_

    `IPython notebook <http://nbviewer.ipython.org/github/yoavram/ipython-notebooks/blob/master/likelihood%20ratio%20test.ipynb>`_
    """
    n0 = m0.ndata
    k0 = m0.nvarys
    chisqr0 = m0.chisqr
    assert chisqr0 > 0, chisqr0
    n1 = m1.ndata
    assert n0 == n1
    k1 = m1.nvarys
    chisqr1 = m1.chisqr
    assert chisqr1 > 0, chisqr1
    Lambda = (old_div(m1.chisqr, m0.chisqr))**(old_div(n0, 2.))
    D = -2 * np.log( Lambda )
    assert D > 0, D
    ddf = k1 - k0
    assert ddf > 0, ddf
    pval = chisqprob(D, ddf)
    prefer_m1 = pval < alfa
    return prefer_m1, pval, D, ddf


def find_max_growth(model_fit, after_lag=True):
    r"""Estimates the maximum population growth rate from the model fit.

    The function calculates the maximum population growth rate :math:`a=\max{\frac{dy}{dt}}` 
    as the derivative of the model curve and calculates its maximum. 
    It also calculates the maximum of the per capita growth rate :math:`\mu = \max{\frac{dy}{y \cdot dt}}`.
    The latter is more useful as a metric to compare different strains or treatments 
    as it does not depend on the population size/density.    

    For example, in the logistic model the population growth rate is a quadratic function of :math:`y` 
    so the maximum is realized when the 2nd derivative is zero:

    .. math::

        \frac{dy}{dt} = r y (1 - \frac{y}{K}) \Rightarrow

        \frac{d^2 y}{dt^2} = r - 2\frac{r}{K}y \Rightarrow

        \frac{d^2 y}{dt^2} = 0 \Rightarrow y = \frac{K}{2} \Rightarrow

        \max{\frac{dy}{dt}} = \frac{r K}{4}

    In contrast, the per capita growth rate a linear function of :math:`y` 
    and so its maximum is realized when :math:`y=y_0`:

    .. math::

        \frac{dy}{y \cdot dt} = r (1 - \frac{y}{K}) \Rightarrow

        \max{\frac{dy}{y \cdot dt}} = \frac{dy}{y \cdot dt}(y=y_0) = r (1 - \frac{y_0}{K})     

    Parameters
    ----------
    model_fit : lmfit.model.ModelResult
        the result of a model fitting procedure
    after_lag : bool
        if true, only explore the time after the lag phase. Otherwise start at time zero. Defaults to :py:const:`True`.

    Returns
    -------
    t1 : float
        the time when the maximum population growth rate is achieved in the units of the `model_fit` ``Time`` variable.
    y1 : float
        the population size or density (OD) for which the maximum population growth rate is achieved.
    a : float
        the maximum population growth rate.
    t2 : float
        the time when the maximum per capita growth rate is achieved in the units of the `model_fit` `Time` variable.
    y2 : float
        the population size or density (OD) for which the maximum per capita growth rate is achieved.
    mu : float
        the the maximum per capita growth rate.
    """
    y0 = model_fit.params['y0'].value
    K  = model_fit.params['K'].value

    t0 = find_lag(model_fit, PLOT=False) if after_lag else 0
    t1 = model_fit.userkws['t'].max()
    t = np.linspace(t0, t1)     
    f = lambda t: model_fit.eval(t=t)
    y = f(t)
    dfdt = derivative(f, t)

    a = dfdt.max()
    i = dfdt.argmax()
    t1 = t[i]
    y1 = y[i]

    dfdt_y = old_div(dfdt, y)
    mu = dfdt_y.max()
    i = dfdt_y.argmax()
    t2 = t[i]
    y2 = y[i]
    
    return t1,y1,a,t2,y2,mu


def find_lag(model_fit, params=None):
    """Estimates the lag duration from the model fit.

    The function calculates the tangent line to the model curve at the point of maximum derivative (the inflection point). 
    The time when this line intersects with :math:`N_0` (the initial population size) 
    is labeled :math:`\lambda` and is called the lag duration time [2]_.

    Parameters
    ----------
    model_fit : lmfit.model.ModelResult
        the result of a model fitting procedure
    params : lmfit.parameter.Parameters, optional
        if provided, these parameters will override `model_fit`'s parameters

    Returns
    -------
    lam : float
        the lag phase duration in the units of the `model_fit` ``Time`` variable (usually hours).    

    References
    ----------
    .. [2] Fig. 2.2 pg. 19 in Baranyi, J., 2010. `Modelling and parameter estimation of bacterial growth with distributed lag time. <http://www2.sci.u-szeged.hu/fokozatok/PDF/Baranyi_Jozsef/Disszertacio.pdf>`_.

    See also
    --------
    :py:func:`find_lag_ci`,
    :py:func:`has_lag`
    """
    if params is None:
        params = model_fit.params
    
    y0 = params['y0'].value
    K  = params['K'].value

    t = model_fit.userkws['t']
    t = np.linspace(t.min(), t.max())
    f = lambda t: model_fit.model.eval(t=t, params=params)
    y = f(t)    
    dfdt = derivative(f, t)
    idx = y > K/np.exp(1)
    assert idx.sum() > 0
    t = t[idx]
    y = y[idx]
    dfdt = dfdt[idx]

    a = dfdt.max()
    i = dfdt.argmax()
    t1 = t[i]
    y1 = y[i]
    b = y1 - a * t1
    lam = (y0 - b) / a
    return lam


def find_lag_ci(model_fit, nsamples=1000, ci=0.95):
    """Estimates a confidence interval for the lag duration from the model fit.

    The function uses *parameteric bootstrap*:
    `nsamples` random parameter sets are sampled using :py:func:`sample_params`.
    The lag duration for each parameter sample is calculated.
    The confidence interval of the lag is the lower and higher percentiles such that 
    `ci` percent of the random lag durations are within the confidence interval.

    Parameters
    ----------
    model_fit : lmfit.model.ModelResult
        the result of a model fitting procedure
    nsamples : int, optional
        number of samples, defaults to 1000
    ci : float, optional
        the fraction of lag durations that should be within the calculated limits. 0 < `ci` <, defaults to 0.95.
    
    Returns
    -------
    low, high : float
        the lower and higher boundries of the confidence interval of the lag phase duration in the units of the `model_fit` ``Time`` variable (usually hours).

    See also
    --------
    :py:func:`find_lag`,
    :py:func:`has_lag`,
    :py:func:`sample_params`
    """
    lam = find_lag(model_fit)
    if not 0 <= ci <= 1:
        raise ValueError("ci must be between 0 and 1")
    lags = np.zeros(nsamples)
    param_samples = sample_params(model_fit, nsamples)
    params = copy.deepcopy(model_fit.params)
    for i in range(param_samples.shape[0]):
        sample = param_samples.iloc[i,:]
        for k,v in params.items():
            if v.vary:
                params[k].set(value=sample[k])
        lags[i] = find_lag(model_fit, params=params)
    
    margin = (1.0 - ci) * 50.0
    idx = np.isfinite(lags) & (lags >= 0)
    if not idx.all():
        warn("Warning: omitting {0} non-finite lag values".format(len(lags) - idx.sum()))
    lags = lags[idx]
    low = np.percentile(lags, margin)
    high = np.percentile(lags, ci * 100.0 + margin)
    assert high > low, lags.tolist()
    return low, high



def has_lag(model_fits, alfa=0.05, PRINT=False):
    r"""Checks if if the best fit has statisticaly significant lag phase :math:`\lambda > 0`.

    If the best fitted model doesn't has a lag phase to begin with, return :py:const:`False`. 
    This includes the logistic model and Richards model.

    Otherwise, a likelihood ratio test will be perfomed with nesting determined according to Figure 1. 
    The null hypothesis of the test is that :math:`\frac{1}{v} = 0` , 
    i.e. the adjustment rate :math:`v` is infinite and therefore there is no lag phase.

    If the null hypothesis is rejected than the function will return :py:const:`True`.
    Otherwise it will return :py:const:`False`.

    Parameters
    ----------
    model_fits : list lmfit.model.ModelResult
        the results of several model fitting procedures, ordered by their statistical preference. Generated by :py:func:`fit_model`.
    alfa : float, optional
        test significance level, defaults to 0.05 = 5%.
    PRINT : bool, optional
        if :py:const:`True`, the function will print the result of the underlying statistical test; defaults to :py:const:`False`.

    Returns
    -------
    bool
        the result of the hypothesis test. :py:const:`True` if the null hypothesis was rejected and the data suggest that there is a significant lag phase.

    Raises
    ------
    ValueError
        raised if the fittest of the :py:class:`lmfit.model.ModelResult` objects in `model_fits` is of an unknown model.
    """
    best_fit = model_fits[0]
    if np.isposinf(best_fit.best_values['q0']) or np.isposinf(best_fit.best_values['v']):
        # no lag in these models
        return False    
    m1 = best_fit
    # choose the null hypothesis model
    nu = best_fit.params['nu']
    v =  best_fit.params['v']
    if nu.value == 1 and not nu.vary:        
        # m1 is BR4 or BR5, m0 is Logistic
        n0 = [m for m in model_fits if m.nvarys == 3]        
    else:
        ## m1 is BR6, m0 is Richards
        m0 = [m for m in model_fits if m.nvarys == 4 and np.isposinf(m.best_values['v'])]        
    prefer_m1, pval, D, ddf = lrtest(m0, m1, alfa=alfa)
    if PRINT:
        print("Tested H0: %s vs. H1: %s; D=%.2g, ddf=%d, p-value=%.2g" % (m0.model.name, m1.model.name, D, ddf, pval))    
    return prefer_m1


def has_nu(model_fits, alfa=0.05, PRINT=False):
    r"""Checks if if the best fit has :math:`\nu \ne 1` and if so if that is statisticaly significant.

    If the best fitted model has :math:`\nu = 1` to begin with, return :py:const:`False`. This includes the logistic model.
    Otherwise, a likelihood ratio test will be perfomed with nesting determined according to Figure 1. 
    The null hypothesis of the test is that :math:`\nu = 1`; if it is rejected than the function will return :py:const:`True`.
    Otherwise it will return :py:const:`False`.

    Parameters
    ----------
    model_fits : list lmfit.model.ModelResult
        the results of several model fitting procedures, ordered by their statistical preference. Generated by :py:func:`fit_model`.
    alfa : float, optional
        test significance level, defaults to 0.05 = 5%.
    PRINT : bool, optional
        if :py:const:`True`, the function will print the result of the underlying statistical test; defaults to :py:const:`False`.

    Returns
    -------
    bool
        the result of the hypothesis test. :py:const:`True` if the null hypothesis was rejected and the data suggest that :math:`\nu` is significantly different from one.

    Raises
    ------
    ValueError
        raised if the fittest of the :py:class:`lmfit.model.ModelResult` objects in `model_fits` is of an unknown model.
    """
    best_fit = model_fits[0]
    if best_fit.best_values['nu'] == 1.0:
        return False
    elif best_fit.nvarys == 4:
        # m1 is Richards, m0 is Logistic        
        m0 = [m for m in model_fits if m.nvarys == 3][0]
    elif best_fit.nvarys == 6:
        # m1 is BR6, m0 is BR5
        m0 = [m for m in model_fits if m.nvarys == 5 and m.best_values['nu'] == 1.0][0]        
    else:
        raise ValueError("Unknown model: %s" % best_fit.model.name)    
    m1 = best_fit
    prefer_m1, pval, D, ddf = lrtest(m0, m1, alfa=alfa)
    if PRINT:
        msg = "Tested H0: %s (nu=%.2g) vs. H1: %s (nu=%.2g); D=%.2g, ddf=%d, p-value=%.2g"  
        print(msg % (m0.model.name, m0.best_values.get('nu', 1), m1.model.name, m1.best_values.get('nu', 1), D, ddf, pval))
    return prefer_m1


def make_Dfun(model, params):
    expr, t, args = model.get_sympy_expr(params)    
    partial_derivs = [None]*len(args)
    for i,x in enumerate(args):
        dydx = expr.diff(x)
        dydx = sympy.lambdify(args=(t,) + args, expr=dydx, modules="numpy")
        partial_derivs[i] = dydx    
    def Dfun(params, y, a, t):
        values = [ par.value for par in params.values() if par.vary ]        
        return np.array([dydx(t, *values) for dydx in partial_derivs])
    return Dfun


def benchmark(model_fits, deltaBIC=6, PRINT=False, PLOT=False):
    """Benchmark a model fit (or the best fit out of a sequence of fits).

    The benchmark is successful -- the model fit is considered "better" then the benchmark fit -- 
    if the `BIC <http://en.wikipedia.org/wiki/Bayesian_information_criterion>`_ of the benchmark fit 
    is higher then the BIC of the model fit by at least `deltaBIC`.
    For typical values of `deltaBIC` and their interpretation, see [3]_. 
    The benchmark is done against a **linear model**. 

    Parameters
    ----------
    model_fits : lmfit.model.ModelResult / list
        one or more results of model fitting procedures. The first element will be benchmarked.
    deltaBIC : float
        the minimal difference in BIC that is interpreted as meaningful evidence in favor of the model fit.
    PLOT : bool, optional
        if :py:const:`True`, the function will plot the model fit and the benchmark fit; defaults to :py:const:`False`.

    Returns
    -------
    passed : bool
        :py:const:`True` if the model fit is significantly better than the benchmark, :py:const:`False` otherwise.
    fig : matplotlib.figure.Figure
        if the argument `PLOT` was :py:const:`True`, the generated figure.
    ax : matplotlib.axes.Axes
        if the argument `PLOT` was :py:const:`True`, the generated axis.

    References
    ----------
    .. [3] Kass, R., Raftery, A., 1995. `Bayes Factors <http://www.tandfonline.com/doi/abs/10.1080/01621459.1995.10476572>`_. J. Am. Stat. Assoc.

    See also
    --------
    Relevant information on `Wikipedia <http://en.wikipedia.org/wiki/Bayesian_information_criterion#Gaussian_Case>`_
    """
    best_fit = model_fits[0] if isinstance(model_fits, collections.Iterable) else model_fits
    t = best_fit.userkws['t']
    y = best_fit.data
    weights = best_fit.weights

    # Linear model used as benchmark
    linear_model = LinearModel()
    linear_model.name = 'linear-benchmark'
    params = linear_model.guess(data=y, x=t)
    linear_fit = linear_model.fit(data=y, x=t, params=params, weights=weights)
    success = best_fit.bic + deltaBIC < linear_fit.bic

    if PRINT:
        print("Model fit: %s, BIC %.2f" % (best_fit.model.name, best_fit.bic))
        print("Benchmark: %s, BIC %.2f" % (linear_fit.model.name, linear_fit.bic))
        print("Fit success: %s" % success)
    if PLOT:
        fig,ax = plt.subplots(1,1)
        ax = best_fit.plot_fit(ax=ax, init_kws={'ls':''})
        linear_fit.plot_fit(ax=ax, init_kws={'ls':''})
        ax.get_legend().set_visible(False)
        ax.set_xlim(0, 1.1 * t.max())
        ax.set_ylim(0.9 * y.min(), 1.1 * y.max())
        ax.set_xlabel('Time')        
        ax.set_ylabel('OD')
        sns.despine()     
        return success, fig, ax
    return success


def cooks_distance(df, model_fit, use_weights=True):
    """Calculates Cook's distance of each well given a specific model fit. 

    Cook's distance is an estimate of the influence of a data curve when performing model fitting; 
    it is used to find wells (growth curve replicates) that are suspicious as outliers.
    The higher the distance, the more suspicious the curve.

    Parameters
    ----------
    df : pandas.DataFrame
        growth curve data, see :py:mod:`curveball.ioutils` for a detailed definition.
    model_fit : lmfit.model.ModelResult
        result of model fitting procedure
    use_weights : bool, optional
        should the function use standard deviation across replicates as weights for the fitting procedure, defaults to :py:const:`True`.

    Returns
    -------
    dict
        a dictionary of Cook's distances: keys are wells (from the `Well` column in `df`), values are Cook's distances.

    See also
    --------
    `Wikipedia <https://en.wikipedia.org/wiki/Cook's_distance>`_
    """
    p = model_fit.nvarys
    MSE = old_div(model_fit.chisqr, model_fit.ndata)
    wells = df.Well.unique()
    D = {}
    
    for well in wells:    
        _df = df[df.Well != well]
        _df = _df.groupby('Time')['OD'].agg([np.mean, np.std]).reset_index()
        weights =  _calc_weights(_df) if use_weights else None
        model_fit_i = copy.deepcopy(model_fit)
        model_fit_i.fit(_df['mean'], weights=weights)
        D[well] = old_div(model_fit_i.chisqr, (p * MSE))
    return D


def find_outliers(df, model_fit, deviations=2, use_weights=True, ax=None, PLOT=False):
    """Find outlier wells in growth curve data.

    Uses the Cook's distance approach (`cooks_distance`); 
    values of Cook's distance that are `deviations` standard deviations **above** the mean
    are defined as outliers.

    Parameters
    ----------
    df : pandas.DataFrame
        growth curve data, see :py:mod:`curveball.ioutils` for a detailed definition.
    model_fit : lmfit.model.ModelResult
        result of model fitting procedure
    deviations : float, optional
        the number of standard deviations that defines an outlier, defaults to 2.
    use_weights : bool, optional
        should the function use standard deviation across replicates as weights for the fitting procedure, defaults to :py:const:`True`.
    ax : matplotlib.axes.Axes, optional
        an axes to plot into; if not provided, a new one is created.
    PLOT : bool, optional
        if :py:const:`True`, the function will plot the Cook's distances of the wells and the threshold.

    Returns
    -------
    outliers : list
        the labels of the outlier wells.
    fig : matplotlib.figure.Figure
        if the argument `PLOT` was :py:const:`True`, the generated figure.
    ax : matplotlib.axes.Axes
        if the argument `PLOT` was :py:const:`True`, the generated axis.
    """
    D = cooks_distance(df, model_fit, use_weights=use_weights)
    D = sorted(D.items()) # TODO SortedDict?
    distances = [x[1] for x in D]        
    dist_mean, dist_std = np.mean(distances), np.std(distances)
    outliers = [well for well,dist in D if dist > dist_mean + deviations * dist_std]
    if PLOT:
        if ax is None:
            fig,ax = plt.subplots(1,1)
        else:
            fig = ax.get_figure()
        wells = [x[0] for x in D]            
        ax.stem(distances, linefmt='k-', basefmt='')
        ax.axhline(y=dist_mean, ls='-', color='k')
        ax.axhline(y=dist_mean + deviations * dist_std, ls='--', color='k')
        ax.axhline(y=dist_mean - deviations * dist_std, ls='--', color='k')
        ax.set_xticks(list(range(len(wells))))
        ax.set_xticklabels(wells, rotation=90)
        ax.set_xlabel('Well')
        ax.set_ylabel("Cook's distance")
        sns.despine()
        return outliers,fig,ax
    return outliers


def find_all_outliers(df, model_fit, deviations=2, max_outlier_fraction=0.1, use_weights=True, PLOT=False):    
    """Iteratively find outlier wells in growth curve data.

    At each iteration, calls :py:func:`find_outliers`.
    Iterations stop when no more outliers are found or when the fraction of wells defined as outliers
    is above `max_outlier_fraction`.
        
    Parameters
    ----------
    df : pandas.DataFrame
        growth curve data, see :py:mod:`curveball.ioutils` for a detailed definition.
    model_fit : lmfit.model.ModelResult
        result of model fitting procedure
    deviations : float, optional
        the number of standard deviations that defines an outlier, defaults to 2.
    max_outlier_fraction : float, optional
        maximum fraction of wells to define as outliers, defaults to 0.1 = 10%.
    use_weights : bool, optional
        should the function use standard deviation across replicates as weights for the fitting procedure, defaults to :py:const:`True`.
    ax : matplotlib.axes.Axes
        an axes to plot into; if not provided, a new one is created.
    PLOT : bool, optional
        if :py:const:`True`, the function will plot the Cook's distances of the wells and the threshold.

    Returns
    -------
    outliers : list
        a list of lists: the list nested at index *i* contains the labels of the outlier wells found at iteration *i*.
    fig : matplotlib.figure.Figure
        if the argument `PLOT` was :py:const:`True`, the generated figure.
    ax : matplotlib.axes.Axes
        if the argument `PLOT` was :py:const:`True`, the generated axis.
    """
    outliers = []
    num_wells = len(df.Well.unique())
    df = copy.deepcopy(df)
    if PLOT:
        fig = plt.figure()
        o, fig, ax = find_outliers(df, model_fit, deviations=deviations, use_weights=use_weights, ax=fig.add_subplot(), PLOT=PLOT)
    else:
        o = find_outliers(df, model_fit, deviations=deviations, use_weights=use_weights, PLOT=PLOT)
    outliers.append(o)
    while len(outliers[-1]) != 0 and len(sum(outliers, [])) <  max_outlier_fraction * num_wells:
        df = df[~df.Well.isin(outliers[-1])]
        assert df.shape[0] > 0, df.shape[0] 
        model_fit = fit_model(df, use_weights=use_weights, PLOT=False, PRINT=False)[0]
        if PLOT:
            o, fig, ax = find_outliers(df, model_fit, deviations=deviations, use_weights=use_weights, ax=fig.add_subplot(), PLOT=PLOT)            
        else:
            o = find_outliers(df, model_fit, deviations=deviations, use_weights=use_weights, PLOT=PLOT)
        outliers.append(o)
    if PLOT:
        return outliers[:-1],fig,ax
    return outliers[:-1]


def _calc_weights(df):
    """If there is more than one replicate, use the standard deviations as weight.
    Warn about NaN and infinite values.
    """
    if np.isnan(df['std']).any():
        warn("Warning: NaN in standard deviations, can't use weights")
        weights = None
    else:
        weights = old_div(1.,df['std'])
        # if any weight is nan, raise error
        idx = np.isnan(weights)
        if idx.any():
            raise ValueError("NaN weights are illegal, indices: " + str(idx))
        # if any weight is infinite, change to the max
        idx = np.isinf(weights)
        if idx.any():
            warn("Warning: found infinite weight, changing to maximum (%d occurences)" % idx.sum())
            weights[idx] = weights[~idx].max()
    return weights


def nvarys(params):
    return len([p for p in params.values() if p.vary])


def fit_model(df, ax=None, param_guess=None, param_min=None, param_max=None, param_fix=None, use_weights=True, use_Dfun=True, PLOT=True, PRINT=True):
    r"""Fit and select a growth model to growth curve data.

    This function fits several growth models to growth curve data (``OD`` as a function of ``Time``).

    Parameters
    ----------
    df : pandas.DataFrame
        growth curve data, see :py:mod:`curveball.ioutils` for a detailed definition.
    ax : matplotlib.axes.Axes, optional
        an axes to plot into; if not provided, a new one is created.
    param_guess : dict, optional
        a dictionary of parameter guesses to use (key: :py:class:`str` of param name; value: :py:class:`float` of param guess).
    param_min : dict, optional
        a dictionary of parameter minimum bounds to use (key: :py:class:`str` of param name; value: :py:class:`float` of param min bound).
    param_max : dict, optional
        a dictionary of parameter maximum bounds to use (key: :py:class:`str` of param name; value: :py:class:`float` of param max bound).
    param_fix : set, optional
        a set of names (:py:class:`str`) of parameters to fix rather then vary, while fitting the models.
    use_weights : bool, optional
        should the function use standard deviation across replicates as weights for the fitting procedure, defaults to :py:const:`True`. 
    use_Dfun : bool, optional
        should the function calculate the partial derivatives of the model functions to be used in the fitting procedure, defaults to :py:const:`False`.
    PLOT : bool, optional
        if :py:const:`True`, the function will plot the all model fitting results.
    PRINT : bool, optional
        if :py:const:`True`, the function will print the all model fitting results.

    Returns
    -------
    models : list
        a list of :py:class:`lmfit.model.ModelResult` objects, sorted by the fitting quality.
    fig : matplotlib.figure.Figure
        figure object.
    ax : numpy.ndarray
        array of :py:class:`matplotlib.axes.Axes` objects, one for each model result, with the same order as `models`.

    Raises
    ------
    TypeError
        if one of the input parameters is of the wrong type (not guaranteed).
    ValueError
        if the input is bad, for example, `df` is empty (not guaranteed).
    AssertionError
        if any of the intermediate calculated values are inconsistent (for example, ``y0<0``).

    Example
    -------
    >>> import curveball
    >>> import pandas as pd
    >>> plate = pd.read_csv('plate_templates/G-RG-R.csv')
    >>> df = curveball.ioutils.read_tecan_xlsx('data/Tecan_280715.xlsx', label='OD', plate=plate)
    >>> green_models = curveball.models.fit_model(df[df.Strain == 'G'])
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("Input df must be a %s, but it is %s" % (pd.DataFrame.__name__, df.__class__.__name__))
    if df.shape[0] == 0:
        raise ValueError("No rows in input df")
    
    if param_guess is None:
        param_guess = dict()
    if param_fix is None:
        param_fix = set()

    _df = df.groupby('Time')['OD'].agg([np.mean, np.std]).reset_index().rename(columns={'mean':'OD'})
    OD = _df.OD.as_matrix()
    time = _df.Time.as_matrix()
    weights =  _calc_weights(_df) if use_weights else None
    results = []
    
    # Baranyi-Roberts = Richards /w lag (6 params)
    br6_model = BaranyiRobertsModel()
    br6_params = br6_model.guess(data=OD, t=time, param_guess=param_guess, param_min=param_min, param_max=param_max, param_fix=param_fix)    
    fit_kws = {'Dfun': make_Dfun(br6_model, br6_params), "col_deriv":True} if use_Dfun else {}
    br6_result = br6_model.fit(data=OD, t=time, params=br6_params, weights=weights, fit_kws=fit_kws)    
    results.append(br6_result)

    # Baranyi-Roberts /w nu=1 = Logistic /w lag (5 params) 
    br5_model = BaranyiRobertsModel()
    _param_guess = param_guess.copy()
    _param_guess['nu'] = 1
    br5_params = br5_model.guess(data=OD, t=time, param_guess=_param_guess, param_min=param_min, param_max=param_max, param_fix=param_fix.union({'nu'}))
    assert br5_params['nu'].value == 1
    fit_kws = {'Dfun': make_Dfun(br5_model, br5_params), "col_deriv":True} if use_Dfun else {}
    br5_result = br5_model.fit(data=OD, t=time, params=br5_params, weights=weights)
    assert br5_result.best_values['nu'] == 1
    results.append(br5_result)

    # Baranyi-Roberts /w nu=1, v=r = Logistic /w lag (4 params)  (see Baty & Delignette-Muller, 2004)
    br4_model = BaranyiRobertsModel()
    _param_guess = param_guess.copy()
    _param_guess['nu'] = 1
    br4_params = br4_model.guess(data=OD, t=time, param_guess=_param_guess, param_min=param_min, param_max=param_max, param_fix=param_fix.union({'nu', 'v'}))
    assert br4_params['nu'].value == 1
    assert br4_params['v'].value == br4_params['r'].value
    fit_kws = {'Dfun': make_Dfun(br4_model, br4_params), "col_deriv":True} if use_Dfun else {}
    br4_result = br4_model.fit(data=OD, t=time, params=br4_params, weights=weights, fit_kws=fit_kws)
    assert br4_result.best_values['v'] == br4_result.best_values['r']
    results.append(br4_result)

    # Richards = Baranyi-Roberts /wout lag (4 params)
    richards_model = BaranyiRobertsModel()
    _param_guess = param_guess.copy()
    _param_guess['v'] = np.inf
    richards_params = richards_model.guess(data=OD, t=time, param_guess=_param_guess, param_min=param_min, param_max=param_max, param_fix=param_fix.union({'q0', 'v'}))
    assert np.isposinf(richards_params['v'].value)
    assert np.isposinf(richards_params['q0'].value)
    fit_kws = {'Dfun': make_Dfun(richards_model, richards_params), "col_deriv":True} if use_Dfun else {}
    richards_result = richards_model.fit(data=OD, t=time, params=richards_params, weights=weights, fit_kws=fit_kws)
    assert np.isposinf(richards_result.best_values['v'])
    assert np.isposinf(richards_result.best_values['q0'])
    results.append(richards_result)

    # Logistic = Richards /w nu = 1 (3 params)
    logistic_model = BaranyiRobertsModel()
    _param_guess = param_guess.copy()
    _param_guess['nu'] = 1
    _param_guess['v'] = np.inf
    logistic_params = logistic_model.guess(data=OD, t=time, param_guess=_param_guess, param_min=param_min, param_max=param_max, param_fix=param_fix.union({'nu', 'q0', 'v'}))
    assert logistic_params['nu'].value == 1
    assert np.isposinf(logistic_params['v'].value)
    assert np.isposinf(logistic_params['q0'].value)
    fit_kws = {'Dfun': make_Dfun(logistic_model, logistic_params), "col_deriv":True} if use_Dfun else {}
    logistic_result = logistic_model.fit(data=OD, t=time, params=logistic_params, weights=weights, fit_kws=fit_kws)
    assert logistic_result.best_values['nu'] == 1
    assert np.isposinf(logistic_result.best_values['v'])
    assert np.isposinf(logistic_result.best_values['q0'])
    results.append(logistic_result)

    # sort by increasing bic
    results.sort(key=lambda m: m.bic)

    if PRINT:
        print(results[0].fit_report(show_correl=False))
    if PLOT:        
        dy = _df.OD.max() / 50.0
        dx = _df.Time.max() / 25.0
        fig, ax = plt.subplots(1, len(results), sharex=True, sharey=True, figsize=(16,6))
        for i,fit in enumerate(results):
            vals = fit.best_values
            fit.plot_fit(ax=ax[i], datafmt='.', fit_kws={'lw':4})
            ax[i].axhline(y=vals.get('y0', 0), color='k', ls='--')
            ax[i].axhline(y=vals.get('K', 0), color='k', ls='--')          
            title = '%s %dp\nBIC: %.3f\ny0=%.2f, K=%.2f, r=%.2g\n' + r'$\nu$=%.2g, $q_0$=%.2g, v=%.2g'
            title = title % (fit.model.name, fit.nvarys, fit.bic, vals.get('y0', 0), vals.get('K', 0), vals.get('r', 0), vals.get('nu',0), vals.get('q0',0), vals.get('v',0))
            ax[i].set_title(title)
            ax[i].get_legend().set_visible(False)
            ax[i].set_xlim(0, 1.1 * _df.Time.max())
            ax[i].set_ylim(0.9 * _df.OD.min(), 1.1 * _df.OD.max())
            ax[i].set_xlabel('Time')
            ax[i].set_ylabel('')
        ax[0].set_ylabel('OD')
        sns.despine()
        fig.tight_layout()
        return results, fig, ax
    return results


if __name__ == '__main__':
    # simulate 30 growth curves
    rng = np.random.RandomState(0)
    t = np.linspace(0, 12)
    reps = 30
    noise = 0.02
    y = baranyi_roberts_function(t=t, y0=0.12, K=0.56, r=0.8, nu=1.8, q0=0.2, v=0.8)
    y.resize((len(t),))
    y = y.repeat(reps).reshape((len(t), reps)) + rng.normal(0, noise, (len(t), reps))
    y[y < 0] = 0
    df = pd.DataFrame({'OD': y.flatten(), 'Time': t.repeat(reps)})

    # fit models to growth curves
    results, fig, ax = fit_model(df, use_Dfun=True, PLOT=True, PRINT=True)
    plt.show()    
