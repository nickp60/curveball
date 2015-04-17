#!/usr/bin/env python
# -*- coding: utf-8 -*-

# This file is part of curveball.
# https://github.com/yoavram/curveball

# Licensed under the MIT license:
# http://www.opensource.org/licenses/MIT-license
# Copyright (c) 2015, Yoav Ram <yoavram+github@gmail.com>
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
sns.set_style("ticks")

from scipy.stats import chisqprob
from lmfit import Model


def logistic_function(t, y0, r, K):
    r"""The logistic growth model is the standard growth model in ecology.

    .. math::
        \frac{dy}{dt} = r y \Big(1 - \frac{y}{K}\Big) \Rightarrow
        y(t) = \frac{K}{1 - \Big(1 - \frac{K}{y_0} \Big)e^{-r t}}


    - :math:`y_0`: initial population size
    - K: maximum population size
    - r: initial growth rate per capita

    See also: `Wikipedia <http://en.wikipedia.org/wiki/Logistic_function>`_
    """
    return richards_function(t ,y0, r, K, 1.)


def richards_function(t, y0, r, K, nu):
    r"""Richards growth model (or the generalized logistic model) in a generalization of the logistic model that allows the inflection point to be anywhere along the curve.

    .. math::

        \frac{dy}{dt} = r y \Big( 1 - \Big(\frac{y}{K}\Big)^{\nu} \Big) \Rightarrow

        y(t) = \frac{K}{\Big[1 - \Big(1 - \Big(\frac{K}{y_0}\Big)^{\nu}\Big) e^{-r \nu t}\Big]^{1/\nu}}

    - :math:`y_0`: initial population size
    - K: maximum population size
    - r: initial growth rate per capita
    - :math:`\nu`: curvature of the logsitic term

    See also: `Wikipedia <http://en.wikipedia.org/wiki/Generalised_logistic_function>`_
    """
    return K / ((1 - (1 - (K/y0)**nu) * np.exp(-r * nu * t))**(1./nu))


def baranyi_roberts_function(t, y0, r, K, nu, q0, v):
    r"""The Baranyi-Roberts growth model is an extension of the Richards model that adds time lag.

    .. math::

        \frac{dy}{dt} = r \alpha(t) y \Big( 1 - \Big(\frac{y}{K}\Big)^{\nu} \Big) \Rightarrow

        y(t) = \frac{K}{\Big[1 - \Big(1 - \Big(\frac{K}{y_0}\Big)^{\nu}\Big) e^{-r \nu A(t)}\Big]^{1/\nu}}

        A(t) = \int_0^t{\alpha(s)ds} = \int_0^t{\frac{q_0}{q_0 + e^{-v t}} ds} = t + \frac{1}{v} \log{\Big( \frac{e^{-v t} + q0}{1 + q0} \Big)}


    - :math:`y_0`: initial population size
    - K: maximum population size
    - r: initial growth rate per capita
    - :math:`\nu`: curvature of the logsitic term
    - :math:`q_0`: initial adjustment to current environment
    - v: adjustment rate

    See also: `Baranyi, J., Roberts, T. a., 1994. A dynamic approach to predicting bacterial growth in food. Int. J. Food Microbiol. 23, 277–294. <www.ncbi.nlm.nih.gov/pubmed/7873331>`_
    """
    At = t + (1./v) * np.log((np.exp(-v * t) + q0)/(1 + q0))
    return K / ((1 - (1 - (K/y0)**nu) * np.exp( -r * nu * At ))**(1./nu))


def simplified_baranyi_roberts_function(t, y0, r, K, q0):
    r"""A four parameter model where $\nu=1$ and $v=r$.
    """
    nu = 1.0
    v = r
    At = t + (1./v) * np.log((np.exp(-v * t) + q0)/(1 + q0))
    return K / ((1 - (1 - (K/y0)**nu) * np.exp( -r * nu * At ))**(1./nu))


def lrtest(m0, m1, alfa=0.05):
    r"""Perform a likelihood ratio test on two nested models.

    For two models, one nested in the other (meaning that the nested model estimated parameters are a subset of the nesting model), the test statistic :math:`D` is:

    .. math::

        \Lambda = \Big( \Big(\frac{\sum{(X_i - \hat{X_i}(\theta_1))^2}}{\sum{(X_i - \hat{X_i}(\theta_0))^2}}\Big)^{n/2} \Big)

        D = -2 log \Lambda

        lim_{n \to \infty} D \sim \chi^2_{df=\Delta}


    where :math:`\Lambda` is the likelihood ratio, :math:`D` is the statistic, :math:`X_{i}` are the data points, :math:`\hat{X_i}(\theta)` is the model prediction with parameters :math:`\theta`, :math:`\theta_i` is the parameters estimation for model :math:`i`, $n$ is the number of data points and :math:`\Delta` is the difference in number of parameters between the models.

    The function compares between two :py:class:`lmfit.ModelFit` objects. These are the results of fitting models to the same data set using the `lmfit <lmfit.github.io/lmfit-py>`_ package

    The function compares between model fit `m0` and `m1` and assumes that `m0` is nested in `m1`, meaning that the set of varying parameters of `m0` is a subset of the varying parameters of `m1`. The property `chisqr` of the :py:class:`ModelFit` objects is the sum of the square of the residuals of the fit. `ndata` is the number of data points. `nvarys` is the number of varying parameters.

    Args:
        - m0, m1: :py:class:`lmfit.Model` objects representing two models. `m0` is nested in `m1`.
        - alfa: The test significance level (default: 5%).

    Returns:
        prefer_m1, pval, D, ddf: :py:class:`tuple`
            - prefer_m1: should we prefer `m1` over `m0`, :py:class:`bool`
            - pval: the test p-value, :py:class:`float`
            - D: the test statistic, :py:class:`float`
            - ddf: the number of degrees of freedom, :py:class:`int`

    See also: `Generalized Likelihood Ratio Test Example <http://www.stat.sc.edu/~habing/courses/703/GLRTExample.pdf>`_, `IPython notebook <http://nbviewer.ipython.org/github/yoavram/ipython-notebooks/blob/master/likelihood%20ratio%20test.ipynb>`_
    """
    n0 = m0.ndata
    k0 = m0.nvarys
    chisqr0 = m0.chisqr
    assert chisqr0 > 0
    n1 = m1.ndata
    assert n0 == n1
    k1 = m1.nvarys
    chisqr1 = m1.chisqr
    assert chisqr1 > 0
    Lambda = (m1.chisqr / m0.chisqr)**(n0 / 2.)
    D = -2 * np.log( Lambda )
    assert D > 0
    ddf = k1 - k0
    assert ddf > 0
    pval = chisqprob(D, ddf)
    prefer_m1 = pval < alfa
    return prefer_m1, pval, D, ddf


def find_lag(model_fit, PLOT=True):
    """Estimates the lag duration from the model fit.

    The function calculates the tangent line to the model curve at the point of maximum derivative (the inflection point). The time when this line intersects with :math:`y0` (the initial population size) is labeled :math:`\lambda` and is called the lag duration time.

    Args:
        - model_fit: :py:class:`lmfit.model.ModelFit` object.
        - PLOT: :py:class:`bool`. If true, the function will plot a figure that illustrates the calculation. Default is :py:const:`False`.

    Returns:
        lam [, fig, ax, ax2]: :py:class:`float` or :py:class:`tuple`
            - lam: :py:class:`float`, the lag phase duration in the unit of the model_fit `Time` varialbe.
            - fig, ax, ax2: if the argument `PLOT` was :py:const:`True`, fig is the generated figure, ax is the left y-axis representing growth, and ax2 is the right y-axis representing growth rate.

    See also: Fig. 2.2 pg. 19 in `Baranyi, J., 2010. Modelling and parameter estimation of bacterial growth with distributed lag time. <http://www2.sci.u-szeged.hu/fokozatok/PDF/Baranyi_Jozsef/Disszertacio.pdf>`_.
    """
    y0 = model_fit.params['y0'].value
    K  = model_fit.params['K'].value

    x = np.linspace(0, 24)
    f = lambda t: fit.eval(t=t)
    y = f(x)
    dfdx = derivative(f, x)

    a = dfdx.max()
    i = dfdx.argmax()
    x1 = x[i]
    y1 = y[i]
    b = y1 - a * x1
    lam = (y0 - b) / a

    if PLOT:
        colors = sns.color_palette('muted', 3)
        fig,ax = subplots()
        ax.plot(x, y, color=colors[0])
        ax.plot(x, y0 + a * (x - lam) , color=colors[1])

        nu = model_fit.params['nu'].value
        q0 = model_fit.params['q0'].value
        v = model_fit.params['v'].value
        r = model_fit.params['r'].value

        ax.plot(x, richards_function(x, y0=y0, r=r, K=K, nu=nu), color=colors[1], ls='--')

        ax2 = ax.twinx()
        ax2.plot(x, dfdx, color=colors[2])
        ax2.plot(x, baranyi_roberts_ode(y, x, r=r, K=K, nu=nu, q0=q0, v=v) , color=colors[2], ls='--')
        ax2.set_ylabel('dOD/dt', color=colors[2])

        ax.set_xlabel('Time')
        ax.set_ylabel('OD', color=colors[0])
        ax.set_ylim(0,1.1)
        ax.axhline(y=y1, color='k', ls='--', alpha=0.5)
        ax.text(x=0.1, y=y1, s="y|max(dydt)")
        ax.axvline(x=x1, color='k', ls='--', alpha=0.5)
        ax.text(x=x1, y=0.01, s="x|max(dydt)")
        ax.axhline(y=y0, color='k', ls='--', alpha=0.5)
        ax.text(x=0.1, y=y0, s="y0")
        ax.axhline(y=K, color='k', ls='--', alpha=0.5)
        ax.text(x=0.1, y=K, s="K")
        ax2.axhline(y=a, color='k', ls='--', alpha=0.5)
        ax2.text(x=14, y=a, s="max(dydt)")
        ax2.axhline(y=r, color='k', ls='--', alpha=0.5)
        ax2.text(x=15, y=r, s="r")
        ax2.axhline(y=(dfdx/y).max(), color='k', ls='--', alpha=0.5)
        ax2.text(x=14, y=(dfdx/y).max(), s="max(dydx/y)")
        ax.axvline(x=lam, color='k', ls='--', alpha=0.5)
        ax.text(x=lam, y=0.01, s=r'$\lambda=$%.2g' % lam)
        sns.despine(top=True, right=False)
        fig.tight_layout()
        ax.set_xlim(0,16)
        return lam,fig,ax,ax2
    return lam



def fit_model(df, ax=None, PLOT=True, PRINT=True):
    r"""Fit a growth model to data.

    This function will attempt to fit a growth model to `OD~Time` taken from the `df` :py:class:`pandas.DataFrame`.
    The function is still being developed.
    """
    _df = df.groupby('Time')['OD'].agg([np.mean, np.std]).reset_index().rename(columns={'mean':'OD'})
    # if there is more than one replicate, use the standard deviation as weight
    if np.isnan(_df['std']).any():
        weights = None
    else:
        weights = 1./_df['std']
    models = []

    # TODO: make MyModel, inherit from Model, use Model.guess
    Kguess  = _df.OD.max()
    y0guess = _df.OD.min()
    nuguess = 1.0
    # TODO replace gradient with scipy.misc.derivate
    _df['dODdTime'] = np.gradient(_df.OD, _df.Time)
    rguess  = 4 * _df.dODdTime[~np.isinf(_df.dODdTime)].max() / Kguess
    q0guess, vguess = 0.1, 1

    params = baranyi_roberts_model.make_params(y0=y0guess, K=Kguess, r=rguess, nu=nuguess, q0=q0guess, v=vguess)
    params['y0'].set(min=1-10)
    params['K'].set(min=1-10)
    params['r'].set(min=1-10)
    params['nu'].set(min=1-10)
    params['q0'].set(min=1e-10, max=1)
    params['v'].set(min=1e-10)

    # Baranyi-Roberts = Richards /w lag (6 params)
    result = baranyi_roberts_model.fit(data=_df.OD, t=_df.Time, params=params, weights=weights)
    models.append(result)

    # Baranyi-Roberts /w nu=1 = Logistic /w lag (5 params)
    params['nu'].set(vary=False)
    result = baranyi_roberts_model.fit(data=_df.OD, t=_df.Time, params=params, weights=weights)
    models.append(result)

    # Simplified Baranyi-Roberts (nu=1, v=t) (4 params)
    # params = simplified_baranyi_roberts_model.make_params(y0=y0guess, K=Kguess, r=rguess, q0=q0guess)
    # params['y0'].set(min=1-10)
    # params['K'].set(min=1-10)
    # params['r'].set(min=1-10)
    # params['q0'].set(min=1-10, max=1)
    # result = simplified_baranyi_roberts_model.fit(data=_df.OD, t=_df.Time, params=params, weights=weights)
    # models.append(result)

    # Richards = Baranyi-Roberts /wout lag (4 params)
    params = richards_model.make_params(y0=y0guess, K=Kguess, r=rguess, nu=nuguess)
    params['y0'].set(min=1-10)
    params['K'].set(min=1-10)
    params['r'].set(min=1-10)
    params['nu'].set(min=1-10)
    result = richards_model.fit(data=_df.OD, t=_df.Time, params=params, weights=weights)
    models.append(result)

    # Logistic = Richards /w nu=1 (3 params)
    params = logistic_model.make_params(y0=y0guess, K=Kguess, r=rguess)
    params['y0'].set(min=1-10)
    params['K'].set(min=1-10)
    params['r'].set(min=1-10)
    result = logistic_model.fit(data=_df.OD, t=_df.Time, params=params, weights=weights)
    models.append(result)

    # sort by increasing bic
    models.sort(key=lambda m: m.bic)

    if PRINT:
        print models[0].fit_report()
        vals = models[0].best_values
        lam = np.log(1. + 1./vals['q0']) / vals['v']
        print "lambda:", lam
    if PLOT:
        dy = _df.OD.max()/50
        dx = _df.Time.max()/25
        fig, ax = plt.subplots(1, len(models), sharex=True, sharey=True, figsize=(16,6))
        for i,fit in enumerate(models):
            vals = fit.best_values
            fit.plot_fit(ax=ax[i], datafmt='.', fit_kws={'lw':4})
            ax[i].axhline(y=vals['y0'], color='k', ls='--')
            ax[i].axhline(y=vals['K'], color='k', ls='--')
            if 'q0' in vals:
                lam = np.log(1. + 1./vals['q0']) / vals['v']
            else:
                lam = 0
            ax[i].axvline(x=lam, color='k', ls='--')
            ax[i].text(x=lam + dx, y=_df.OD.min() - 3*dy, s=r'$\lambda=$%.2f' % lam)
            title = '%s %dp\nBIC: %d\ny0=%.2f, K=%.2f, r=%.2g\n' + r'$\nu$=%.2g, $q_0$=%.2g, v=%.2g'
            title = title % (fit.model.name, fit.nvarys, fit.bic, vals['y0'], vals['K'], vals['r'], vals.get('nu',0), vals.get('q0',0), vals.get('v',0))
            ax[i].set_title(title)
            ax[i].get_legend().set_visible(False)
            ax[i].set_xlim(0, 1.1 * _df.Time.max())
            ax[i].set_ylim(0, 1.1 * _df.OD.max())
            ax[i].set_xlabel('Time')
            ax[i].set_ylabel('')
        ax[0].set_ylabel('OD')
        sns.despine()
        fig.tight_layout()
        return models, fig, ax
    return models


logistic_model = Model(logistic_function)
richards_model = Model(richards_function)
baranyi_roberts_model = Model(baranyi_roberts_function)
simplified_baranyi_roberts_model = Model(simplified_baranyi_roberts_function)
