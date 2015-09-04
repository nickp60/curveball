#!/usr/bin/env python
# -*- coding: utf-8 -*-

# This file is part of curveball.
# https://github.com/yoavram/curveball

# Licensed under the MIT license:
# http://www.opensource.org/licenses/MIT-license
# Copyright (c) 2015, Yoav Ram <yoav@yoavram.com>
import os.path
import glob
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
sns.set_style("ticks")
import click
import curveball

PLOT = False
ERROR_COLOR = 'red'
file_extension_handlers = {'.mat': curveball.ioutils.read_tecan_mat}


def echo_error(message):
	click.secho("Error: %s" % message, fg=ERROR_COLOR)


def process_file(filepath, plate, blank_strain, ref_strain, max_time):
	results = []
	click.echo('Filename: %s' % click.format_filename(filepath))
	fn,ext = os.path.splitext(filepath)
	click.echo('Extension: %s' % ext)
	handler = file_extension_handlers.get(ext)
	click.echo('Handler: %s' % handler.__name__)
	if  handler == None:
		click.echo("No handler")
		return results

	try: 
		df = handler(filepath, plate=plate, max_time=max_time)
	except IOError as e:
		echo_error('Failed reading data file, %s' % e.message)
		return results

	if PLOT:
		wells_plot_fn = fn + '_wells.png'
		curveball.plots.plot_wells(df, output_filename=wells_plot_fn)
		click.echo("Wrote wells plot to %s" % wells_plot_fn)

		strains_plot_fn = fn + '_strains.png'
		curveball.plots.plot_strains(df, output_filename=strains_plot_fn)
		click.echo("Wrote strains plot to %s" % strains_plot_fn)

	strains = plate.Strain.unique().tolist()
	strains.remove(ref_strain)
	strains.insert(0, ref_strain)	

	for strain in strains:		
		strain_df = df[df.Strain == strain]
		_ = curveball.models.fit_model(strain_df, PLOT=PLOT, PRINT=False)
		if PLOT:
			fit_results,fig,ax = _
			strain_plot_fn = fn + ('_strain_%s.png' % strain)
			fig.savefig(strain_plot_fn)
			click.echo("Wrote strain %s plot to %s" % (strain, strain_plot_fn))
		else:
			fit_results = _

		res = {}
		fit = fit_results[0]
		res['file'] = fn
		res['strain'] = strain
		res['model'] = fit.model.name
		res['bic'] = fit.bic
		res['aic'] = fit.aic
		params = fit.params
		res['y0'] = params['y0'].value
		res['K'] = params['K'].value
		res['r'] = params['r'].value
		res['nu'] = params['nu'].value if 'nu' in params else 1
		res['q0'] = params['q0'].value if 'q0' in params else 0
		res['v'] = params['v'].value if 'v' in params else 0
		res['max_growth_rate'] = curveball.models.find_max_growth(fit, PLOT=False)[-1]
		res['lag'] = curveball.models.find_lag(fit, PLOT=False)
		res['has_lag'] = curveball.models.has_lag(fit_results)
		res['has_nu'] = curveball.models.has_nu(fit_results, PRINT=False)
		#res['benchmark'] = curveball.models.benchmark(fit) # FIXME

		if strain == ref_strain:
			ref_fit = fit
			res['w'] = 1
		else:
			colors = plate[plate.Strain.isin([strain, ref_strain])].Color.unique()
			_ = curveball.competitions.compete(fit, ref_fit, hours=df.Time.max(), colors=colors, PLOT=PLOT)
			if PLOT:
				t,y,fig,ax = _
				competition_plot_fn = fn + ('_%s_vs_%s.png' % (strain, ref_strain))
				fig.savefig(competition_plot_fn)
				click.echo("Wrote competition %s vs %s plot to %s" % (strain, ref_strain, strain_plot_fn))
			else:
				t,y = _
			res['w'] = curveball.competitions.fitness_LTEE(y, assay_strain=0, ref_strain=1)

		results.append(res)
	return results


def process_folder(folder, plate_path, blank_strain, ref_strain, max_time):
	results = []
	try:
		plate = pd.read_csv(plate_path)
	except IOError as e:
		echo_error('Failed reading plate file, %s' % e.message)
		return results
	plate.Strain = map(unicode, plate.Strain)
	plate_strains = plate.Strain.unique().tolist()
	click.echo("Plate with %d strains: %s" % (len(plate_strains), ', '.join(plate_strains)))
	fig,ax = curveball.plots.plot_plate(plate)
	fig.show()
	click.confirm('Is this the plate you wanted?', default=False, abort=True, show_default=True)

	files = glob.glob(os.path.join(folder, '*'))
	files = filter(lambda fn: os.path.splitext(fn)[-1].lower() in file_extension_handlers.keys(), files)
	if not files:
		echo_error("No files found in folder %s" % folder)
		return results

	for fn in files:
		filepath = os.path.join(folder, fn)
		file_results = process_file(filepath, plate, blank_strain, ref_strain, max_time)
		results.extend(file_results)

	return results


@click.command()
@click.option('--folder', prompt=True, help='folder to process')
@click.option('--plate_folder', default='plate_templates', help='plate templates default folder')
@click.option('--plate_file', default='checkerboard.csv', help='plate templates csv file')
@click.option('--blank_strain', default='0', help='blank strain for background calibration')
@click.option('--ref_strain', default='1',  help='reference strain for competitions')
@click.option('--max_time', default=np.inf, help='omit data after max_time hours')
@click.option('-v/-V', '--verbose/--no-verbose', default=True)
def main(folder, plate_folder, plate_file, blank_strain, ref_strain, max_time, verbose):
	if verbose:		
		click.secho('=' * 40, fg='cyan')
		click.secho('Curveball %s' % curveball.__version__, fg='cyan')	
		click.secho('=' * 40, fg='cyan')
		click.echo('- Processing %s' % click.format_filename(folder))
		plate_path = os.path.join(plate_folder, plate_file)
		click.echo('- Using plate template from %s' % click.format_filename(plate_path))
		click.echo('- Blank strain: %s; Reference strain: %s' % (blank_strain, ref_strain))
		click.echo('- Omitting data after %.2f hours' % max_time)
		click.echo('-' * 40)

	results = process_folder(folder, plate_path, blank_strain, ref_strain, max_time)
	df = pd.DataFrame(results)
	output_filename = os.path.join(folder, 'curveball.csv')
	df.to_csv(output_filename, index=False)
	click.secho("Wrote output to %s" % output_filename, fg='green')


if __name__ == '__main__':
    main()