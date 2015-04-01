"""
Matplotlib microplate visualization
----------------------
A simple microplate implementation in matplotlib.
Based on https://jakevdp.github.io/blog/2012/12/06/minesweeper-in-matplotlib/

Author: Yoav Ram <yoavram@gmail.com>, Mar. 2015
License: BSD
"""
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import RegularPolygon
import seaborn as sns

class Plate(object):
	edge_color = '#888888'
	bg_color = "#95a5a6"    
	ABCD = 'ABCDEFGHIJKLMNOPQRSTUVQXYZ'

	@classmethod
	def ninety_six_wells(cls, nstrains=2):
		return cls(12, 8, nstrains)

	@classmethod
	def from_csv(cls, filename):
		strains = np.loadtxt(filename, dtype=object, delimiter=', ')
		strains = np.rot90(strains, 3)				
		nstrains = len(np.unique(strains))
		palette = sns.color_palette("Set1", nstrains)

		plate = cls(strains.shape[0], strains.shape[1], nstrains)
		plate.strains = strains
		plate.colors  = {0: '#ffffff'}

		for i in range(plate.width):
			for j in range(plate.height):
				strain = strains[i,j]
				# if number, parse to int
				try:
					strain = int(strain)
					strains[i,j] = strain
				except ValueError:
					pass
				# if not already in colors, set color
				if strain not in plate.colors:
					plate.colors[strain] = palette.pop()
				# get color and paint the well
				color = plate.colors[strain]
				plate.squares[i,j].set_facecolor(color)
		return plate
	

	def to_csv(self, fname):        
		return np.savetxt(fname, np.rot90(self.strains), fmt='%d', delimiter=', ')


	def to_array(self):
		return np.rot90(self.strains)


	def __repr__(self):
		return str(self.to_array())
  

	def __init__(self, width, height, nstrains):
		self.width, self.height, self.nstrains = width, height, nstrains    
		
		# Create the figure and axes
		self.fig = plt.figure(figsize=((width + 2) / 3., (height + 2) / 3.))
		self.ax = self.fig.add_axes((0.05, 0.05, 0.9, 0.9),
									aspect='equal', frameon=False,
									xlim=(-0.05, width + 0.05),
									ylim=(-0.05, height + 0.05))
		for axis in (self.ax.xaxis, self.ax.yaxis):
			axis.set_major_formatter(plt.NullFormatter())
			axis.set_major_locator(plt.NullLocator())

		# Create the grid of squares
		self.squares = np.array([[RegularPolygon((i + 0.5, j + 0.5),
												 numVertices=4,
												 radius=0.5 * np.sqrt(2),
												 orientation=np.pi / 4,
												 ec=self.edge_color,
												 fc=self.bg_color)
								  for j in range(height)]
								 for i in range(width)])
		[self.ax.add_patch(sq) for sq in self.squares.flat]  
		self.strains = np.zeros((width, height), dtype=int)
		# Create event hook for mouse clicks
		self.fig.canvas.mpl_connect('button_press_event', self._button_press)
				
	
	def _click_square(self, i, j):        
		col = self.strains[i,j]
		col = (col + 1) % self.nstrains
		self.strains[i,j] = col
		col = self.colors[col]                
		self.squares[i,j].set_facecolor(col)


	def _button_press(self, event):
		if (event.xdata is None) or (event.ydata is None):
			return
		i, j = map(int, (event.xdata, event.ydata))
		if (i < 0 or j < 0 or i >= self.width or j >= self.height):
			return       
		self._click_square(i, j)
		self.fig.canvas.draw()


	def well2strain(self, well):
		'''well: a string of letter+number'''
		j = int(well[1:]) - 1 # zero count
		letter = well[0]
		i = self.ABCD.index(letter.upper())
		return self.to_array()[i,j]


if __name__ == '__main__':
	import sys
	if len(sys.argv) > 1:
		nstrains = int(sys.argv[1])			
	else:
		nstrains = 3
	print "# strains:", nstrains
	plate = Plate.ninety_six_wells(nstrains)
	plt.show()
	fname = raw_input("Plate filename?\n")
	plate.to_csv(fname)