# Liam Bessell, 2/8/21

import os
import sys

import numpy as np

import honeybee_radiance.reader as reader
from honeybee_radiance.geometry import Polygon
from honeybee_radiance.modifier.material import Plastic
from honeybee_radiance.view import View

def getDimensionLength(quad : Polygon, dimensionIndex : int) -> int:
    """
    Returns the length of the quad on this dimension.
    e.g. If dimensionIndex=0, then we return the difference between
    max_x and min_x, which is the dimension's length
    """
    min = float("inf")
    max = float("-inf")
    for vertex in quad.vertices:
        if vertex[dimensionIndex] < min:
            min = vertex[dimensionIndex]
        if vertex[dimensionIndex] > max:
            max = vertex[dimensionIndex]
    
    if min < 0 and max < 0:
        return abs(min) - abs(max)
    elif min < 0 and max > 0:
        return max + abs(min)
    else:
        return max - min

def getQuadNormal(quad : Polygon) -> []:
    """
    v1        v4
    +---------+
    |         | 
    |         |
    +---------+
    v2        v3
    
    Taking the cross product of v2-v1 and v4-v1
    Since it's a quad, the surface normal is the same throughout
    """
    vectorA = []
    vectorB = []
    for i in range(3):
        vectorA.append(quad.vertices[1][i] - quad.vertices[0][i])
        vectorB.append(quad.vertices[3][i] - quad.vertices[0][i])
    
    normal = np.cross(vectorA, vectorB)
    if np.linalg.norm(normal) != 0:
        normal = normal / np.linalg.norm(normal)
        return list(normal)
    else:
        return []

def getViewPosition(quad : Polygon, dimensions : [], normal : []) -> []:
    """
    Returns the view position for the parallel projection view
    """
    # First we get the dimension minimums. We add the length of the dimension / 2 to this to get the view position
    # e.g. If the minimum for x is -2 and the quad's dimensions for x are 5, then the view position will
    # be at 0.5 for x
    dimensionMinimums = [float("inf"), float("inf"), float("inf")]
    for i in range(3):
        for vertex in quad.vertices:
            if vertex[i] < dimensionMinimums[i]:
                dimensionMinimums[i] = vertex[i]

    viewPosition = []
    for i in range(3):
        if dimensions[i] > 0.0001:
            viewPosition.append(dimensionMinimums[i] + dimensions[i] / 2)
        else:
            # We can use any of the quad's vertices, because they all have the same value for this dimension
            viewPosition.append(quad.vertices[0][i] + normal[i])
    
    return viewPosition

def main():
    argc = len(sys.argv)
    if argc < 2:
        print("Error: .rad file not specified, usage: python radToParallelProjections.py <my_file.rad>")
        return -1
    
    filePath = sys.argv[1]
    if not filePath.endswith(".rad"):
        print("Error: .rad file not specified, usage: python radToParallelProjections.py <my_file.rad>")
        return -1

    stringObjects = reader.parse_from_file(filePath)
    polygons = []
    materials = []
    currentModifier = None
    for stringObject in stringObjects:
        # This is a bit hacky right now. We get an exception if we try and parse a non-material or non-polygon
        if not "plastic" in stringObject and not "polygon" in stringObject:
            continue

        primitiveDict = reader.string_to_dict(stringObject)
        if primitiveDict["type"] == "polygon":
            primitiveDict["modifier"] = None
            polygon = Polygon.from_primitive_dict(primitiveDict)
            polygon.modifier = currentModifier
            polygons.append(polygon)
        elif primitiveDict["type"] == "plastic":
            plastic = Plastic.from_primitive_dict(primitiveDict)
            currentModifier = plastic
            materials.append(plastic)

    triangles = []
    quads = []
    for polygon in polygons:
        if len(polygon.vertices) == 3:
            triangles.append(polygon)
        elif len(polygon.vertices) == 4:
            quads.append(polygon)

    for quad in quads:
        # type 'l' defines this view as a parallel projection
        view = View(quad.identifier, type='l')

        # Get the dimensions of the quad. 
        # One of these should be approximately 0.0
        dimensions = [0, 0, 0]
        for i in range(3):
            dimensions[i] = getDimensionLength(quad, i)
        
        # Set the view's horizontal and vertical size based on the dimensions of the quad
        # The projection will contain the entire quad
        horizontalSet = False
        verticalSet = False
        for i in range(3):
            # Accounting for floating point errors
            if dimensions[i] > 0.0001:
                if not horizontalSet:
                    view.h_size = dimensions[i]
                    horizontalSet = True
                else:
                    view.v_size = dimensions[i]
                    verticalSet = True
                    break
        if not horizontalSet and not verticalSet:
            print("Error: " + view.identifier + " vh and/or vv not set")
            continue

        # Set view direction
        normal = getQuadNormal(quad)
        if len(normal) == 0:
            print("Error: " + view.identifier + " vn not set")
            continue
        direction = (-normal[0], -normal[1], -normal[2])
        view.direction = direction

        # Set view position
        position = getViewPosition(quad, dimensions, normal)
        view.position = position

        # Set view up


        print("view=" + view.identifier + " " + view.to_radiance())

    return 0

if __name__ == "__main__":
    main()