from scipy import spatial
from pylab import *;
from . import utils

def nearestIndices(xcenters, ycenters, knotTree):
    """
        Args:
        xcenters (array): array of x coordinates of each center.
        ycenters (array): array of y coordinates of each center.
        knotTree (spatial.KDTree): spatial.KDTree(knots)
        Returns:
        array: array of arrays, each with the indices of the 4 nearest knots to each element in x/y-centers.
        """
    return array([utils.nearest(xc,yc, 4, knotTree) for xc,yc in zip(xcenters, ycenters)])


def createGrid(xcenters, ycenters, xBinSize, yBinSize):
    """
    :param point_list:  array of lists with (x,y) coordinates of each center.
    :param xBinSize: x length of each rectangle in the knot grid.
    :param yBinSize: y length of each rectangle in the knot grid.
    :return: array of lists with (x,y) coordinates of each vertex in knot grid.
    """
    xmin, xmax = min(xcenters), max(xcenters)
    ymin, ymax = min(ycenters), max(ycenters)
    return [(x, y) for x in arange(xmin, xmax, xBinSize) for y in arange(ymin, ymax, yBinSize)]

def associateFluxes(knots, nearIndices, xcenters, ycenters, fluxes):
    """
    Args:
        :param knots: array of lists with (x,y) coordinates of each vertex in the knot grid.
        :param nearIndices: array of arrays, each with the indices of the 4 nearest knots to each element in y/x-centers.
        :param xcenters: array of lists with x coordinates of each center.
        :param ycenters: array of lists with y coordinates of each center.
        :param fluxes: array of fluxes corresponding to each element in x/y-centers.
    :return:
        Array with the mean flux associated with each knot of the grid.
    """
    knot_fluxes = [[] for k in knots]
    for kp in range(len(xcenters)):
        N = nearIndices[kp][0]
        knot_fluxes[N].append(fluxes[kp])
    return [mean(flux) if len(flux) is not 0 else 0 for flux in knot_fluxes]

def generate_deltaX_deltaY(xcenters, ycenters, knots, nearIndices):
    """
        :param xcenters: array of lists with x coordinates of each center.
        :param ycenters: array of lists with y coordinates of each center.
        :param knots: array of lists with (x,y) coordinates of each vertex in the knot grid.
        :param nearIndices: array of arrays, each with the indices of the 4 nearest knots to each element in y/x-centers.
    """
    deltaX1 = zeros(len(xcenters))
    deltaY1 = zeros(len(ycenters))
    for kp, (xc,yc) in enumerate(zip(xcenters, ycenters)):
        deltaX1[kp] = abs(xc - knots[nearIndices[kp][0]][0])
        deltaY1[kp] = abs(yc - knots[nearIndices[kp][0]][1])

    return deltaX1, deltaY1

def interpolateFlux(knots, knotFluxes, deltaX1, deltaY1, nearIndices, xBinSize, yBinSize, normFactor):
    """
        Args:
        knots (array): array of lists with (x,y) coordinates of each vertex in the knot grid.
        knotFluxes (array): array of the flux associated with each knot.
        deltaX1 (array): array with delta x-coordinates of each center to knot1_X.
        deltay1 (array): array with delta y-coordinates of each center to knot1_Y.
        nearIndices (array): array of arrays, each with the indices of the 4 nearest knots to each element in x/y-centers.
        xBinSize (float): x length of each rectangle in the knot grid.
        yBinSize (float): y length of each rectangle in the knot grid.
        normFactor (float): (1/xBinSize) * (1/yBinSize)
        Returns:
        array: array of interpolated flux at each point in x/y-centers.
    """
    interpolated_fluxes = np.zeros(len(deltaX1))
    for kp, (dx1,dy1) in enumerate(zip(deltaX1, deltaY1)):
        nearest_fluxes = [knotFluxes[i] for i in nearIndices[kp]]
        # If any knot has no flux, use nearest neighbor interpolation.
        if 0 in nearest_fluxes:
            N = nearIndices[kp][0]
            interpolated_fluxes[kp] = knotFluxes[N]
        # Else, do bilinear interpolation
        else:
            # Normalize distances with factor
            # Interpolate
            dx2 = xBinSize - dx1
            dy2 = xBinSize - dy1

            interpolated_fluxes[kp] = normFactor * (dx1 * dy2 * nearest_fluxes[0]
                                                  + dx2 * dy2 * nearest_fluxes[1]
                                                  + dx2 * dy1 * nearest_fluxes[2]
                                                  + dx1 * dy1 * nearest_fluxes[3])
    return interpolated_fluxes

def BLISS(xcenters, ycenters, fluxes, knots, nearIndices, xBinSize=0.01, yBinSize=0.01, normFactor=10000):
    """
        Args:
        xcenters (array): array of x-coordinates of each center.
        ycenters (array): array of y-coordinates of each center.
        fluxes (array): array of fluxes corresponding to each element in x/y-centers.
        knots (array): array of lists with (x,y) coordinates of each vertex in the knot grid.
        nearIndices (array): array of arrays, each with the indices of the 4 nearest knots to each element in x/y-centers.
        xBinSize (float): x length of each rectangle in the knot grid.
        yBinSize (float): y length of each rectangle in the knot grid.
        normFactor (float): (1/xBinSize) * (1/yBinSize)
        Returns:
        array: array of interpolated flux at each point in x/y-centers.
        """
    meanKnotFluxes = associateFluxes(knots, nearIndices, xcenters, ycenters, fluxes)
    deltaX1, deltaY1 = generate_deltaX_deltaY(xcenters, ycenters, knots, nearIndices)

    return interpolateFlux(knots=knots, knotFluxes=meanKnotFluxes, deltaX1=deltaX1, deltaY1=deltaY1, nearIndices=nearIndices, xBinSize=xBinSize, yBinSize=yBinSize, normFactor=normFactor)
