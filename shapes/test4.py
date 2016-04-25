import matplotlib.pyplot as plt

plt.axvspan(76, 76, facecolor='g', alpha=1)
plt.annotate('This is awesome!',
             xy=(76, 0.75))
             #xycoords='data'
             #textcoords='offset points')
             #arrowprops=dict(arrowstyle="->"))
plt.show()