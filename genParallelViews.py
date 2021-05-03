# Liam Bessell

import sys
from datetime import datetime
import numpy as np

import honeybee_radiance.reader as reader
from honeybee_radiance.geometry import Polygon
from honeybee_radiance.modifier.material import Plastic
from honeybee_radiance.modifier.material import Metal
from honeybee_radiance.modifier.material import Glass
from honeybee_radiance.view import View

##### Global constants
# Modify the following variables depending on your implementation

# This is the desired file name for the OBJ and MTL files
BASE_FILE_NAME = "scene"

# This is the prefix (if any) for the Radiance renderings. 
# If using a RIF script to generate the renderings, search for a PICTURE entry.
# The prefix is the final non-directory portion of the path.
# e.g. "PICTURE=pictures/scene", in this case "scene" is the prefix
RIF_PICTURE_PREFIX = "scene"

# The UP vector for the scene in Radiance
SCENE_UP = [0.0, 0.0, 1.0]

# Used in floating point error calculations
SIGMA = 0.0001

# Used for parsing the RAD file
VALID_MATERIALS = ["plastic", "metal", "glass"]
#####

def listsSame(listA : [], listB : []) -> bool:
    """
    Returns true if the lists' elements are equal to eachother
    """
    if len(listA) != len(listB):
        return False

    for i in range(len(listA)):
        if not (listA[i] < listB[i] + SIGMA and listA[i] > listB[i] - SIGMA):
            return False

    return True

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

def getTriangleNormal(triangle : Polygon) -> []:
    """
    v1        
    +
    |\
    | \         
    |  \     
    +---+
    v2  v3
    
    Taking the cross product of v1-v2 and v2-v3
    """
    vectorA = []
    vectorB = []
    for i in range(3):
        vectorA.append(triangle.vertices[0][i] - triangle.vertices[1][i])
        vectorB.append(triangle.vertices[2][i] - triangle.vertices[1][i])
    
    normal = np.cross(vectorA, vectorB)
    if np.linalg.norm(normal) != 0:
        normal = normal / np.linalg.norm(normal)
        return list(normal)
    else:
        return []

def formsQuad(triangleA : Polygon, triangleB : Polygon) -> bool:
    """
    Returns true if these triangles share two vertices.
    i.e. these two triangles together make up a quad
    """
    duplicateVerts = []
    for i in range(3):
        vertexA = triangleA.vertices[i]
        for j in range(3):
            vertexB = triangleB.vertices[j]
            if listsSame(vertexA, vertexB):
                duplicateVerts.append(vertexA)
                if len(duplicateVerts) == 2:
                    return True
                break
    
    return False

def formQuad(triangleA : Polygon, triangleB : Polygon) -> Polygon:
    """
    Forming a quad out of two complementary triangles
    """
    vertices = [[], [], [], []]
    vertices[0] = triangleA.vertices[0]
    vertices[1] = triangleA.vertices[1]
    vertices[3] = triangleA.vertices[2]

    # First we search for the unique vertex in triangle B
    for i in range(len(triangleB.vertices)):
        isDuplicate = False
        vertexB = triangleB.vertices[i]
        for j in range(len(triangleA.vertices)):
            vertexA = triangleA.vertices[j]
            if listsSame(vertexB, vertexA):
                isDuplicate = True
                break

        # Once we find the vertex unique to the second triangle, we assign it and break out
        if not isDuplicate:
            vertices[2] = vertexB
            break
    
    # Next we check if the vertex ordering needs to be switched
    # This is necessary when two or more elements switch from one vertex to the next
    for i in range(3):
        differentElements = 0
        for j in range(3):
            if vertices[i][j] < vertices[i+1][j] - SIGMA or vertices[i][j] > vertices[i+1][j] + SIGMA:
                differentElements += 1

        # Swap
        if differentElements > 1:
            # Note that this could throw an index error for the first and last vertices, but during my testing this has been a sufficient workaround
            tmp = vertices[i-1]
            vertices[i-1] = vertices[i]
            vertices[i] = tmp
            break

    quad = Polygon(triangleA.identifier, vertices)
    quad.modifier = triangleA.modifier
    return quad

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
        if dimensions[i] > SIGMA:
            viewPosition.append(dimensionMinimums[i] + dimensions[i] / 2)
        else:
            # We can use any of the quad's vertices, because they all have the same value for this dimension
            viewPosition.append(quad.vertices[0][i] + 0.1 * normal[i])
    
    return viewPosition

def writeOBJFile(fileName : str, quads : [], viewDict : {}):
    with open(fileName + ".obj", "w") as f:
        f.write("# Parallel Projection OBJ File\n# Generated at {0}\n\nmtllib {1}.mtl\n\n".format(datetime.now(), fileName))
        faceCtr = 1
        for quad in quads:
            view = viewDict[quad.identifier]
            normal = getQuadNormal(quad)
            vertices = quad.vertices
            if len(RIF_PICTURE_PREFIX) != 0:
                f.write("usemtl {0}_{1}_texture\n".format(RIF_PICTURE_PREFIX, quad.identifier))
            else:
                f.write("usemtl {0}_texture\n".format(quad.identifier))
            f.write("v {0:.3f} {1:.3f} {2:.3f}\nv {3:.3f} {4:.3f} {5:.3f}\nv {6:.3f} {7:.3f} {8:.3f}\nv {9:.3f} {10:.3f} {11:.3f}\n".format(vertices[0][0], vertices[0][1], vertices[0][2],
                                                                                                                                            vertices[1][0], vertices[1][1], vertices[1][2],
                                                                                                                                            vertices[2][0], vertices[2][1], vertices[2][2],
                                                                                                                                            vertices[3][0], vertices[3][1], vertices[3][2]))
            viewUp = [val for val in view.up_vector]
            if listsSame(viewUp, SCENE_UP):
                f.write("vt 0 0\nvt 1 0\nvt 1 1\nvt 0 1\n")
            else:
                # This is also a bit hacky, but it works so far
                # A better assignment of vt coordinates is, however, desired
                f.write("vt 1 0\nvt 1 1\nvt 0 1\nvt 0 0\n")
            f.write("vn {0:.3f} {1:.3f} {2:.3f}\nvn {0:.3f} {1:.3f} {2:.3f}\nvn {0:.3f} {1:.3f} {2:.3f}\nvn {0:.3f} {1:.3f} {2:.3f}\n".format(normal[0], normal[1], normal[2]))
            f.write("f {0}/{0}/{0} {1}/{1}/{1} {2}/{2}/{2} {3}/{3}/{3}\n\n".format(faceCtr, faceCtr+1, faceCtr+2, faceCtr+3))
            faceCtr += 4
        
        print("Created {0}.obj".format(fileName))

def writeMTLFile(fileName : str, quads : []):
    with open(fileName + ".mtl", "w") as f:
        f.write("# Parallel Projection Texture MTL File\n# Generated at {0}\n\n".format(datetime.now()))
        for quad in quads:
            if len(RIF_PICTURE_PREFIX) != 0:
                f.write("newmtl {0}_{1}_texture\nKa 1.000 1.000 1.000\nKd 1.000 1.000 1.000\nd 1.0\nillum 1\nmap_Kd {0}_{1}.hdr\n\n".format(RIF_PICTURE_PREFIX, quad.identifier))
            else: 
                f.write("newmtl {0}_texture\nKa 1.000 1.000 1.000\nKd 1.000 1.000 1.000\nd 1.0\nillum 1\nmap_Kd {0}.hdr\n\n".format(quad.identifier))
        
        print("Created {0}.mtl".format(fileName))

def main():
    argc = len(sys.argv)
    if argc < 2:
        print("Error: .rad file not specified, usage: python3 genParallelViews.py <file.rad>")
        return -1
    
    filePath = sys.argv[1]
    if not filePath.endswith(".rad"):
        print("Error: .rad file not specified, usage: python3 genParallelViews.py <file.rad>")
        return -1

    print("Scene up direction: [{0}, {1}, {2}]".format(SCENE_UP[0], SCENE_UP[1], SCENE_UP[2]))

    # Read in the RAD file
    stringObjects = reader.parse_from_file(filePath)
    polygons = []
    materials = []
    currentModifier = None
    for stringObject in stringObjects:
        if not "polygon" in stringObject:
            validMaterial = False
            for material in VALID_MATERIALS:
                if material in stringObject:
                    validMaterial = True
                    break
            
            # This is a bit hacky right now. We get an exception if we try and parse a non-material or non-polygon
            if not validMaterial:
                print("Error: Can't parse '{0}' from RAD file. If this is a material try manually adding it to the script, else ignore.".format(stringObject))
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
        elif primitiveDict["type"] == "metal":
            metal = Metal.from_primitive_dict(primitiveDict)
            currentModifier = metal
            materials.append(metal)
        elif primitiveDict["type"] == "glass":
            glass = Glass.from_primitive_dict(primitiveDict)
            currentModifier = glass
            materials.append(glass)
        else:
            print("Error: Unable to assign material from '{0}'.".format(stringObject))

    # Loop through all the polygons read in from the RAD file and classify them as triangles or quads
    triangles = []
    quads = []
    for polygon in polygons:
        if len(polygon.vertices) == 3:
            triangles.append(polygon)
        elif len(polygon.vertices) == 4:
            quads.append(polygon)

    # Loop through all the triangles read in from the RAD file and attempt to form quads from them
    trianglesMissed = []
    i = 0
    while True:
        if i >= len(triangles) - 1:
            break

        triangleA = triangles[i]
        triangleB = triangles[i+1]
        if formsQuad(triangleA, triangleB):
            quad = formQuad(triangleA, triangleB)
            quads.append(quad)
            i += 2
        else:
            trianglesMissed.append(triangleA)
            i += 1

    if len(trianglesMissed) != 0:    
        print("The following triangles from the RAD file couldn't be formed into quads: ", end="")
        for triangle in trianglesMissed:
            print("{0}".format(triangle.identifier), end=" ")
        print()
    
    # Loop through all the quads and generate a Radiance parallel projection view for it
    viewDict = {}
    for quad in quads:
        # type 'l' defines this view as a parallel projection
        view = View(quad.identifier, type='l')
         
        # Get the dimensions of the quad. 
        # One of these should be approximately 0.0 because a quad is two dimensional
        dimensions = [0, 0, 0]
        for i in range(3):
            dimensions[i] = getDimensionLength(quad, i)
        
        # Set the view's horizontal and vertical size based on the dimensions of the quad
        # The projection will contain the entire quad
        horizontalSet = False
        verticalSet = False
        for i in range(3):
            if dimensions[i] > SIGMA:
                if not horizontalSet:
                    view.h_size = dimensions[i]
                    horizontalSet = True
                else:
                    view.v_size = dimensions[i]
                    verticalSet = True
                    break
        
        if not horizontalSet or not verticalSet:
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
        view.up_vector = SCENE_UP
        if listsSame(SCENE_UP, direction) or listsSame(SCENE_UP, normal):
            if not listsSame(SCENE_UP, [0.0, 0.0, 1.0]):
                view.up_vector = [0.0, 0.0, 1.0]
            elif not listsSame(SCENE_UP, [0.0, 1.0, 0.0]):
                view.up_vector = [0.0, 1.0, 0.0]
            else:
                view.up_vector = [1.0, 0.0, 0.0]

        viewDict[quad.identifier] = view

    print("\n-----Radiance Parallel Views-----")
    for view in viewDict.values():
        print("view=" + view.identifier + " " + view.to_radiance())
    print("----------\n\nTotal view count: {0}, Total quad count: {1}".format(len(viewDict.values()), len(quads)))

    writeOBJFile(BASE_FILE_NAME, quads, viewDict)
    writeMTLFile(BASE_FILE_NAME, quads)

    return 0

if __name__ == "__main__":
    main()