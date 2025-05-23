from flask import Flask, render_template, request, redirect, url_for, session
import json
import os
import GlobalData as GD
from flask import jsonify
from engineio.payload import Payload
from PIL import Image
import csv
from io import StringIO

from distutils.dir_util import copy_tree

import re

# functions to calculate lon/lat to xyz for the DataDiVR 
import numpy as np 
from math import cos, radians, sin, sqrt
from scipy.spatial.transform import Rotation as rot
from sklearn import preprocessing




def geodetic_to_geocentric(latitude, longitude):
    """Return geocentric (Cartesian) Coordinates x, y, z corresponding to
    the geodetic coordinates given by latitude and longitude (in
    degrees) and height above ellipsoid. The ellipsoid must be
    specified by a pair (semi-major axis, reciprocal flattening).

    """

    # Ellipsoid parameters: semi major axis in metres, reciprocal flattening.
    ellipsoid = 6378137, 298.257223563
    height = 124

    φ = radians(latitude)
    λ = radians(longitude)
    sin_φ = sin(φ)
    a, rf = ellipsoid           # semi-major axis, reciprocal flattening
    e2 = 1 - (1 - 1 / rf) ** 2  # eccentricity squared
    n = a / sqrt(1 - e2 * sin_φ ** 2) # prime vertical radius
    r = (n + height) * cos(φ)   # perpendicular distance from z axis
    x = r * cos(λ)
    y = r * sin(λ)
    z = (n * (1 - e2) + height) * sin_φ

    return x,-y,z


def normalize_xyz(coords):

    # normalize coordinates to fit into range 0-1
    x = [i[0] for i in coords] 
    y = [i[1] for i in coords] 
    z = [i[2] for i in coords]
    x_norm = preprocessing.minmax_scale(list(x), feature_range=(0,1), axis=0, copy=True)
    y_norm = preprocessing.minmax_scale(list(y), feature_range=(0,1), axis=0, copy=True)
    z_norm = preprocessing.minmax_scale(list(z), feature_range=(0,1), axis=0, copy=True)

    return x_norm,y_norm,z_norm

def hex_to_rgb(hx):
    hx=hx.lstrip('#')
    hlen=len(hx)
    return tuple(int(hx[i:i+hlen//3], 16) for i in range(0,hlen//3))





def check_ProjectFolder():
    path = "static/projects/GD.json"
    if not os.path.isfile(path):
        print("GD.json not found, copying demo_project")
        copy_tree("static/demo_project", "static/projects")

def makeProjectFolders(name):
    path = "static/projects/" + name
    pfile = {}
    pfile["name"] = name
    pfile["layouts"] = []
    pfile["layoutsRGB"] = []
    pfile["links"] = []
    pfile["linksRGB"] = []
    pfile["selections"] = []

    try:
        os.mkdir(path)
        os.mkdir(path + '/layouts')
        os.mkdir(path + '/layoutsl')
        os.mkdir(path + '/layoutsRGB')
        os.mkdir(path + '/links')
        os.mkdir(path + '/linksRGB')
        os.mkdir(path + '/legends')

        with open(path + '/pfile.json', 'w') as outfile:
            json.dump(pfile, outfile)

    except OSError:
        print ("Creation of the directory %s failed" % path)
    else:
        print ("Successfully created the directory %s " % path)

def loadProjectInfo(name):
    folder = 'static/projects/' + name + '/'
    layoutfolder = folder + "layouts"
    layoutRGBfolder = folder + "layoutsRGB"
    linksRGBfolder = folder + "linksRGB"
    linkfolder = folder + "links"

    if os.path.exists(folder):

        layouts = [name for name in os.listdir(layoutfolder)]
        layoutsRGB = [name for name in os.listdir(layoutRGBfolder)]
        links = [name for name in os.listdir(linkfolder)]
        linksRGB = [name for name in os.listdir(linksRGBfolder)]

        return jsonify(
            layouts=layouts,
            layoutsRGB=layoutsRGB,
            links = links,
            linksRGB = linksRGB 
        )
    else:
        return 'no such project'

        
def loadAnnotations(name):
    namefile = 'static/projects/' + name + '/names.json'
    f = open(namefile)
    data = json.load(f)
    return data






def makeXYZTexture(project, pixeldata, name=None): 

    hight = 128 * (int((len(pixeldata["data"])) / 16384) + 1)

    print ("hight is " + str(hight))
    size = 128 * hight 
    path = 'static/projects/' + project 
    
    texh = [(0,0,0)] * size
    texl = [(0,0,0)] * size

    if "_geo" in pixeldata["name"]:
        #print("is geo")
        unscaled = []
        # convert lat lon to XYZ
        for x in pixeldata["data"]:
            unscaled.append(geodetic_to_geocentric(float(x[0]), float(x[1])))
        # Normalize to 0-1 range
        scaled = normalize_xyz(unscaled)
        
        for i in range(len(scaled[0])):
            
            x = int(float(scaled[0][i])*65280)
            y = int(float(scaled[1][i])*65280)
            z = int(float(scaled[2][i])*65280)

            xh = int(x / 255)
            yh = int(y / 255)
            zh = int(z / 255)

            xl = x % 255
            yl = y % 255
            zl = z % 255

            pixelh = (xh,yh,zh)
            pixell = (xl,yl,zl)

            texh[i] = pixelh
            texl[i] = pixell
            #print(pixelh)
    
    else:
       
        x_norm = []
        y_norm = []
        z_norm = []
        for i in range(len(pixeldata["data"])):
                
            x = float(pixeldata["data"][i][0])
            y = float(pixeldata["data"][i][1])
            z = float(pixeldata["data"][i][2])
            
            x_norm.append(x)
            y_norm.append(y)
            z_norm.append(z)

        # check on coordinates - if normalized
        #print("C_DEBUG: checking for coords if normed or not.")
        
        if min(x_norm)<0 or min(y_norm)<0 or min(z_norm)<0 or max(x_norm)>1 or max(y_norm)>1 or max(z_norm)>1:
            coordinates_norm = normalize_xyz(pixeldata["data"]) 
            #print("C_DEBUG: coordinates_norm: ", coordinates_norm)
            for i in range(len(coordinates_norm[0])):
                        
                x = int(float(coordinates_norm[0][i])*65280)
                y = int(float(coordinates_norm[1][i])*65280)
                z = int(float(coordinates_norm[2][i])*65280)

                xh = int(x / 255)
                yh = int(y / 255)
                zh = int(z / 255)

                xl = x % 255
                yl = y % 255
                zl = z % 255

                pixelh = (xh,yh,zh)
                pixell = (xl,yl,zl)

                texh[i] = pixelh
                texl[i] = pixell
                #print(pixelh)
                #print("C_DEBUG: normalized coordinates.")

        else:
            #print("C_DEBUG: pixeldata: ", pixeldata["data"])
            for i in range(len(pixeldata["data"])):

                x = int(float(pixeldata["data"][i][0])*65280)
                y = int(float(pixeldata["data"][i][1])*65280)
                z = int(float(pixeldata["data"][i][2])*65280)

                xh = int(x / 255)
                yh = int(y / 255)
                zh = int(z / 255)

                xl = x % 255
                yl = y % 255
                zl = z % 255

                pixelh = (xh,yh,zh)
                pixell = (xl,yl,zl)

                texh[i] = pixelh
                texl[i] = pixell
                #print(pixelh)
                #print("C_DEBUG: DID NOT normalize coordinates.")

    new_imgh = Image.new('RGB', (128, hight))
    new_imgl = Image.new('RGB', (128, hight))

    new_imgh.putdata(texh)
    new_imgl.putdata(texl)

    pathXYZ = path + '/layouts/' +  pixeldata["name"] + 'XYZ.bmp'
    pathXYZl = path + '/layoutsl/' +  pixeldata["name"]  + 'XYZl.bmp' 
    if name is not None:
        pathXYZ = path + '/layouts/' +  name + '.bmp'
        pathXYZl = path + '/layoutsl/' +  name  + 'l.bmp' 

    ### integrate name 
    #if os.path.exists(pathXYZ):
        #return '<a style="color:red;">ERROR </a>' + pixeldata["name"]  + " Nodelist already in project"
    #else:
    new_imgh.save(pathXYZ)
    new_imgl.save(pathXYZl)
    return '<a style="color:green;">SUCCESS </a>' + pixeldata["name"]  + " Node Textures Created"

def makeNodeRGBTexture(project, pixeldata, name=None): 

    # check if data is rgba or hex string
    for i in (pixeldata["data"]):
        rgba_colors = []
        if type(i) is str and len(i) == 6 and i.startswith('#'):
            rgba_converted = hex_to_rgb(pixeldata["data"][i]) 
            rgba_colors.append(rgba_converted)
        else:
            rgba_colors = pixeldata["data"]

    hight = 128 * (int((len(pixeldata["data"])) / 16384) + 1)

    print ("hight is " + str(hight))
    size = 128 * hight 
    path = 'static/projects/' + project 
    tex = [(128,0,0,100)] * size

    for i in range(len(rgba_colors)): #pixeldata["data"])):
        #tex[i] = (int(pixeldata["data"][i][0]), int(pixeldata["data"][i][1]),int(pixeldata["data"][i][2]),int(pixeldata["data"][i][3]))
        tex[i] = (int(rgba_colors[i][0]), int(rgba_colors[i][1]),int(rgba_colors[i][2]),int(rgba_colors[i][3]))

    new_img = Image.new('RGBA', (128, hight))
    new_img.putdata(tex)
    pathXYZ = path + '/layoutsRGB/' +  pixeldata["name"] + 'RGB.png'
    if name is not None:
        pathXYZ = path + '/layoutsRGB/' +  name +  '.png'

    #if os.path.exists(pathXYZ):
        #return '<a style="color:red;">ERROR </a>' + pixeldata["name"]  + " colors already in project"
    #else:
    new_img.save(pathXYZ , "PNG")
    return '<a style="color:green;">SUCCESS </a>' + pixeldata["name"]  + " Node Textures Created"
    


def makeLinkTexNew(project,  name, links, linkcol): 
    print((len(links["data"])) / 32768)
    hight = 64 * (int((len(links["data"])) / 32768) + 1)
    print("image hight = " + str(hight))
    #hight = 512 #int(elem / 512)+1
    path = 'static/projects/' + project 

    texl = [(0,0,0)] * 1024 * hight
    new_imgl = Image.new('RGB', (1024, hight))
    i = 0

    linklist = {}
    linklist["links"] = []
    try:
        for row in links["data"]:
            thislink = {}
            thislink["id"] = i
            thislink["s"] = row[0]
            thislink["e"] = row[1]
            linklist["links"].append(thislink)

            sx = int(row[0]) % 128 # R
            syl = int(int(row[0]) / 128) % 128 # G
            syh = int(int(row[0]) / 16384) # B

            ex = int(row[1]) % 128
            eyl = int(int(row[1]) / 128) % 128
            eyh = int(int(row[1]) / 16384)


            pixell1 = (sx,syl,syh)
            pixell2 = (ex,eyl,eyh)

            #if i < 262144:

            texl[i*2] = pixell1
            texl[i*2+1] = pixell2

            i += 1

    except (IndexError, ValueError):
        return '<a style="color:red;">ERROR </a>'  +  links["name"] + " Linkfile malformated?" 

    with open(path + '/links.json', 'w') as outfile:
        json.dump(linklist, outfile)

    new_imgl.putdata(texl)
    pathl = path + '/links/' +  links["name"] + 'XYZ.bmp'
    if name is not None:
        pathl = path + '/links/' +  name +  '.bmp'

    #if os.path.exists(pathl):
        #return '<a style="color:red;">ERROR </a>' +  links["name"]  + " linklist already in project"
    #else:
    new_imgl.save(pathl)
    return '<a style="color:green;">SUCCESS </a>' +  links["name"] +  " Link Textures Created"
 



def makeLinkRGBTex(project, linksRGB, name=None):
    
    hight = 64 * (int((len(linksRGB["data"])) / 32768) + 1)
    path = 'static/projects/' + project 
    rgba_colors = []
    # check if data is rgba or hex string
    try:
        for i in (linksRGB["data"]):
            rgba_colors = []
            if type(i) is str and len(i) == 6 and i.startswith('#'):
                rgba_converted = hex_to_rgb(linksRGB["data"][i]) 
                rgba_colors.append(rgba_converted)
            else: 
                rgba_colors = linksRGB["data"]

    except: # quick fix - if only point cloud upload and no links
        
        print("has no colors")

    texc = [(0,0,0,0)] * 512 * hight

    new_imgc = Image.new('RGBA', (512, hight))
    i = 0

    linklist = {}
    linklist["links"] = []
    try:
        for row in rgba_colors: #linksRGB["data"]:
            #if i < 262144:
            texc[i]  = (int(row[0]),int(row[1]),int(row[2]),int(row[3]))
            i += 1

    except (IndexError, ValueError):
        return '<a style="color:red;">ERROR </a>'  +  linksRGB["name"] + " Linkfile malformated?" 

    new_imgc.putdata(texc)
    pathRGB = path + '/linksRGB/' +  linksRGB["name"] +  'RGB.png'
    if name is not None:
        pathRGB = path + '/linksRGB/' +  name +  '.png'

    #if os.path.exists(pathRGB):
        #return '<a style="color:red;">ERROR </a>' +  linksRGB["name"]  + " linklist already in project"
    #else:
    new_imgc.save(pathRGB, "PNG")
    return '<a style="color:green;">SUCCESS </a>' +  linksRGB["name"] +  " Link Textures Created"
 





def upload_filesNew(request):
    #print("C_DEBUG: namespace", request.args.get("namespace"))
    form = request.form.to_dict()
    #print(request.files)
    #print(form)
    prolist = GD.plist

    namespace = form["new_name"]
    if not namespace:
        return "namespace fail"
    
    if namespace in prolist:
        print('project exists')
    else:
        # Make Folders
        makeProjectFolders(namespace)

    folder = 'static/projects/' + namespace + '/'
    pfile = {}

    with open(folder + 'pfile.json', 'r') as json_file:
        pfile = json.load(json_file)
    json_file.close()

    state = ''
    nodelist = {"nodes":[]}

    nodepositions = []
    nodecolors = []
    links = []
    linkcolors = []
    nodeinfo = []
    labels = []

    parsefiles(request.files.getlist("nodesXYZ"), nodepositions)      
    parsefiles(request.files.getlist("nodesRGB"), nodecolors)  
    parsefiles(request.files.getlist("links"), links)      
    parsefiles(request.files.getlist("linksRGB"), linkcolors)
    parsefiles(request.files.getlist("nprop"), nodeinfo)
    parsefiles(request.files.getlist("labels"), labels)

    #----------------------------------
    # FOR GRAPH TITLE + DESCRIPTION 
    #----------------------------------
    title_of_graph = namespace
    descr_of_graph = ""

    numnodes = len(nodepositions[0]["data"])

    # generate node.json
    for i in range(len(nodepositions[0]["data"])):
        thisnode = {}
        thisnode["id"] = i
        if "_geo" in nodepositions[0]["name"]:
            thisnode["lat"] = nodepositions[0]["data"][i][0]
            thisnode["lon"] = nodepositions[0]["data"][i][1]

        if len(nodeinfo[0]["data"]) == len(nodepositions[0]["data"]):
            thisnode["attrlist"] = nodeinfo[0]["data"][i]
            thisnode["n"] = str(nodeinfo[0]["data"][i][0])
        else:
            thisnode["attrlist"] = ["node" + str(i)]
            thisnode["n"] = "node" + str(i)

        nodelist["nodes"].append(thisnode)

    for labellist in labels:   
        name = ""
        i = 0
        for row in labellist["data"]:
            name = row[0]
            row.pop(0)
            # add to nodes.json
            thisnode = {}
            thisnode["id"] = i + numnodes
            thisnode["group"] = row
            thisnode["n"] = str(name)
            nodelist["nodes"].append(thisnode)
            #add to pfile
            pfile["selections"].append({"name":name, "nodes":row})
            # get average pos for Each layout
            for layout in nodepositions:
                accPos = [0,0,0]
                pos = [0,0,0]
                
                for x in row:

                    # catch for 2D positions for labels and for empty rows
                    if len(x) > 0 and len(layout["data"][int(x)]) == 3:
                        accPos[0] += float(layout["data"][int(x)][0])
                        accPos[1] += float(layout["data"][int(x)][1])
                        accPos[2] += float(layout["data"][int(x)][2])
                    
                    elif len(x) > 0 and len(layout["data"][int(x)]) == 2: 
                        accPos[0] += float(layout["data"][int(x)][0])
                        accPos[1] += float(layout["data"][int(x)][1])
                        accPos[2] += 0.0

                pos[0] = str(accPos[0] / len(row))
                pos[1] = str(accPos[1] / len(row))
                pos[2] = str(accPos[2] / len(row))
                layout["data"].append(pos)

            # label nodes to be black
            for color in nodecolors:
                color["data"].append((0,0,0,0)) #255,0,0,100
            i += 1


    for layout in nodepositions:
        if len(layout["data"])> 0:
            state =  state + makeXYZTexture(namespace, layout) + '<br>'
            pfile["layouts"].append(layout["name"] + "XYZ")

        # catch for 2D positions and for empty rows
        elif len(layout["data"]) > 0 and len(layout["data"][int(x)]) == 2:
            for i,xy in enumerate(layout["data"]):
                layout["data"][i] = (xy[0],xy[1],0.0)
            state =  state + makeXYZTexture(namespace, layout) + '<br>'
            pfile["layouts"].append(layout["name"] + "XYZ")

        else: state = "upload must contain at least 1 node position list"

    for color in nodecolors:
        
        if len(color["data"]) == 0:
            color["data"] = [[255,0,255,100]] * numnodes
            color["name"] = "nan"

        state =  state + makeNodeRGBTexture(namespace, color) + '<br>'
        pfile["layoutsRGB"].append(color["name"]+ "RGB")

    for linklist in links:
        if len(linklist["data"]) == 0:
            linklist["name"] = "nan"
        state =  state + makeLinkTexNew(namespace, linklist) + '<br>'
        pfile["links"].append(linklist["name"]+ "XYZ")

    for lcolors in linkcolors:
        if len(lcolors["data"]) == 0:
            lcolors["data"] = [[255,0,255,100]] * len(links[0]["data"])
            lcolors["name"] = "nan"
        state =  state + makeLinkRGBTex(namespace, lcolors) + '<br>'
        pfile["linksRGB"].append(lcolors["name"]+ "RGB")

    pfile["nodecount"] = numnodes
    pfile["labelcount"] = len(labels[0]["data"])
    pfile["linkcount"] = len(links[0]["data"])

    #----------------------------------
    # adding graph info to pfile 
    #----------------------------------
    pfile["graphtitle"] = title_of_graph
    pfile["graphdesc"] = descr_of_graph

    #----------------------------------
    # uploading and storing Legends files in folder
    # and adding filenames to pfile 
    #----------------------------------
    legendfiles = []
    loadLegendFiles(request.files.getlist("legendFiles"), folder+'legends/', legendfiles)
    pfile["legendfiles"] = legendfiles



    with open(folder + '/pfile.json', 'w') as outfile:
        json.dump(pfile, outfile)

    with open(folder + '/nodes.json', 'w') as outfile:
        json.dump(nodelist, outfile)
    
    GD.plist =GD.listProjects()
    return state



def parsefiles(files, target):
    if len(files) > 0:     
        for file in files:
            content = file.read().decode('utf-8')
            vecList = {}
            vecList["data"] = []
            vecList["name"] = file.filename.split(".")[0]
            lines = content.splitlines()
            for line in lines:
                vecList["data"].append(line.split(","))  
            target.append(vecList)
            #print(vecList) 



# -------------------------------------------
# upload Images via Uploader
# -------------------------------------------
def loadLegendFiles(files, legendfolder, target):
    try: 
        if len(files) > 0: 
            path = legendfolder
            for file in files:
                file.save(os.path.join(path, file.filename))
                target.append(file.filename)
        else: 
            print("C_DEBUG: Error - files list is empty.")

    except Exception as e:
        print("") #C_DEBUG: Error in loadLegendFiles. ", e)






























































##########################  OLD UPLOADER DONT USE  ##########################





def upload_files(request):
    form = request.form.to_dict()

    prolist = GD.plist
    namespace = '' 
    if form["namespace"] == "New":
        namespace = form["new_name"]    #namespace
    else:
        namespace = form["existing_namespace"]
    if not namespace:
        return "namespace fail"
    
    # GET LAYOUT
    
    if namespace in prolist:
        print('project exists')
    else:
        # Make Folders
        makeProjectFolders(namespace)


    folder = 'static/projects/' + namespace + '/'
    pfile = {}

    with open(folder + 'pfile.json', 'r') as json_file:
        pfile = json.load(json_file)
    json_file.close()


    state = ''

    labels_content = ""
    

    label_file = request.files.getlist("labels")
    if len(label_file) > 0:     
        for file in label_file:
            name = file.filename.split(".")[0]
            labels_content = file.read().decode('utf-8')
            print(labels_content)
            lines = labels_content.splitlines()
            for line in lines:
                thislabelText = line.split(";")[0]
                thislabel = line.split(";")[1]
                thislabelNodes = thislabel.split(",")

                newsel = {}
                newsel["name"] = thislabelText
                newsel["nodes"] = thislabelNodes
                pfile["selections"].append(newsel)
        #pfile["labelcount"] = len(pfile["selections"])
    else:
        print("error parsing labels")




    layout_files = request.files.getlist("layouts")

    if len(layout_files) > 0 and len(layout_files[0].filename) > 0:
        #print("loading layouts", len(layout_files))
        #print(layout_files[0])
        
        for file in layout_files:
            # TODO: fix the below line to account for dots in filenames
            name = file.filename.split(".")[0]
            contents = file.read().decode('utf-8')
            out = makeNodeTex(namespace, name, contents, labels_content)
            state = state + ' <br>'+ out[0]

            #clumsy way to do it
            pfile['labels'] = [out[1],out[2]]
            pfile['nodecount'] = out[1]
            pfile['labelcount'] = out[2]

            pfile["layouts"].append(name + "XYZ")
            pfile["layoutsRGB"].append(name + "RGB")
         
            # print(contents)
            #x = validate_layout(contents.split("\n"))
            #print("layout errors are", x)
            #if x[1] == 0:
            
        #Upload.upload_layouts(namespace, layout_files)


    # GET EDGES
    edge_files = request.files.getlist("links")
    if len(edge_files) > 0 and len(edge_files[0].filename) > 0:
        print("loading links", len(edge_files))
        #Upload.upload_edges(namespace, edge_files)
        for file in edge_files:
            name = file.filename.split(".")[0]
            contents = file.read().decode('utf-8')
            pfile["links"].append(name + "XYZ")
            pfile["linksRGB"].append(name + "RGB")
            out = makeLinkTex(namespace, name, contents)
            pfile["linkcount"] = out[1]
            state = state + ' <br>'+ out[0]
    #GET Labels

    #update the projects file
    with open(folder + 'pfile.json', 'w') as json_file:
        json.dump(pfile, json_file)

    #global sessionData
    #sessionData["proj"] = listProjects()
    GD.plist =GD.listProjects()
    return state



















import shutil

def update_files(pname, nodelist, linklist, Npos, Ncol, links, linkcol):
    #form = request.form.to_dict()

    prolist = GD.plist
    namespace = pname
    
    # GET LAYOUT
    
    folder = 'static/projects/' + namespace + '/'
    if os.path.exists(folder):
        shutil.rmtree(folder)
    
        # Make Folders
    makeProjectFolders(namespace)

    pfile = {}

    state = ''

    labels_content = ""
    
    '''
    label_file = request.files.getlist("labels")

    if len(label_file) > 0:     
        for file in label_file:
            name = file.filename.split(".")[0]
            labels_content = file.read().decode('utf-8')
            print(labels_content)
            lines = labels_content.splitlines()
            for line in lines:
                thislabelText = line.split(";")[0]
                thislabel = line.split(";")[1]
                thislabelNodes = thislabel.split(",")

                newsel = {}
                newsel["name"] = thislabelText
                newsel["nodes"] = thislabelNodes
                pfile["selections"].append(newsel)
        #pfile["labelcount"] = len(pfile["selections"])
    else:
        print("error parsing labels")

    '''


    layout_files = [Npos]
    print(layout_files)
    if len(layout_files) > 0 :

        #print("loading layouts", len(layout_files))
        #print(layout_files[0])
        
        for file in layout_files:
            print(layout_files)
            # TODO: fix the below line to account for dots in filenames
            name = "test"
            
            makeNodeTex(pname, name, file, "None")
             
            #clumsy way to do it
            '''
            pfile['labels'] = [out[1],out[2]]
            pfile['nodecount'] = out[1]
            pfile['labelcount'] = out[2]

            pfile["layouts"].append(name + "XYZ")
            pfile["layoutsRGB"].append(name + "RGB")
            '''
            # print(contents)
            #x = validate_layout(contents.split("\n"))
            #print("layout errors are", x)
            #if x[1] == 0:
            
        #Upload.upload_layouts(namespace, layout_files)

    '''
    # GET EDGES
    edge_files = request.files.getlist("links")
    if len(edge_files) > 0 and len(edge_files[0].filename) > 0:
        print("loading links", len(edge_files))
        #Upload.upload_edges(namespace, edge_files)
        for file in edge_files:
            name = file.filename.split(".")[0]
            contents = file.read().decode('utf-8')
            pfile["links"].append(name + "XYZ")
            pfile["linksRGB"].append(name + "RGB")
            out = makeLinkTex(namespace, name, contents)
            pfile["linkcount"] = out[1]
            state = state + ' <br>'+ out[0]
    #GET Labels

    #update the projects file
    with open(folder + 'pfile.json', 'w') as json_file:
        json.dump(pfile, json_file)

    #global sessionData
    #sessionData["proj"] = listProjects()
    GD.plist =GD.listProjects()
    return state






    '''








def updatePfile(project, nodelist,labellist, linklist):
    pfile = {}
    with open("static/projects/"+ project + "/pfile.json", "r") as f:
        pfile = json.load(f)

        folders = ["layouts","layoutsRGB","links", "linksRGB"]

        for f in folders:
            llist = os.listdir("static/projects/"+ project + "/"+f+"/")
            newlist = []
            for l in llist:
                x = l.split(".")
                newlist.append(x[0])

            pfile[f] = newlist

        pfile["nodecount"] = len(nodelist) - len(labellist)
        pfile["linkcount"] = len(linklist)
        pfile["labelcount"] = len(labellist)
        pfile["selections"] = []

        for x in labellist:
            thissel = {"name":x["n"],"nodes":x["group"]}
            pfile["selections"].append(thissel)
            #print(thissel)
    #f.close()


    with open("static/projects/"+ project + "/pfile.json", 'w') as x:
        json.dump(pfile, x)
        print(pfile)








import math

def makeLinkTex(project, name, links,linkcol):
    
    hight = 64 * (math.floor((len(links)) / 32768) + 1)
    path = 'static/projects/' + project 
    print(hight)
    texl = [(0,0,0)] * 1024 * hight
    texc = [(0,0,0,0)] * 512 * hight
    new_imgl = Image.new('RGB', (1024, hight))
    new_imgc = Image.new('RGBA', (512, hight))
    i = 0

    linklist = {}
    linklist["links"] = []

    for i in range(len(links)):

        thislink = {}
        thislink["id"] = i
        thislink["s"] = links[i][0]
        thislink["e"] = links[i][1]
        linklist["links"].append(thislink)

        sx = int(links[i][0]) % 128 # R
        syl = int(int(links[i][0]) / 128) % 128 # G
        syh = int(int(links[i][0]) / 16384) # B

        ex = int(links[i][1]) % 128
        eyl = int(int(links[i][1]) / 128) % 128
        eyh = int(int(links[i][1]) / 16384)

        #if len(linkcol) == 6:

        r = int(linkcol[i][0])
        g = int(linkcol[i][1])
        b = int(linkcol[i][2])
        a = int(linkcol[i][3])


        pixell1 = (sx,syl,syh)
        pixell2 = (ex,eyl,eyh)
        pixelc = (r,g,b,a)

        #if i < 262144:

        texl[i*2] = pixell1
        texl[i*2+1] = pixell2
        texc[i] = pixelc

        #i += 1

   # except (IndexError, ValueError):
    #    return '<a style="color:red;">ERROR </a>'  +  name + " Linkfile malformated?" 

    with open(path + '/links.json', 'w') as outfile:
        json.dump(linklist, outfile)

    new_imgl.putdata(texl)
    new_imgc.putdata(texc)
    pathl = path + '/links/' +  name + 'XYZ.bmp'
    pathRGB = path + '/linksRGB/' +  name +  'RGB.png'

    #if os.path.exists(pathl):
    #    return '<a style="color:red;">ERROR </a>' +  name  + " linklist already in project"
    #else:
    new_imgl.save(pathl, "PNG")
    new_imgc.save(pathRGB, "PNG")
    #    return '<a style="color:green;">SUCCESS </a>' +  name +  " Link Textures Created" , len(linklist["links"])
    return "successfully created node textures and names file"

















def makeNodeTex(project, name, nodelistIn,labellist, nodepos, nodecol):
    #print(labelfile)
    



    hight = 128 * (int((len(nodepos)) / 16384) + 1)

    print ("hight is " + str(hight))
    size = 128 * hight 
    path = 'static/projects/'+project 
    
    texh = [(0,0,0)] * size
    texl = [(0,0,0)] * size
    texc = [(0,0,0,0)] * size

    new_imgh = Image.new('RGB', (128, hight))
    new_imgl = Image.new('RGB', (128, hight))
    new_imgc = Image.new('RGBA', (128, hight))
    
    i = 0
    attrlist = {}
    attrlist['names'] = []
    nodelist = {"nodes":[]}


    

    for label in labellist:
        #print(row)
        thiscolor = [200,200,200]
        #thisnode = {"id":label["id"]}
        label["name"] = "reee"

        pos = [0,0,0]
        
        for n in label["group"]:
        #if ";" in row[0]:
        # A LIST OF NODES
            #my_list = row[0].split(";")
            #row[0] = my_list[1]
            #print(my_list)
            accPos = [0,0,0]
            
            accPos[0] += nodepos[int(n)][0]
            accPos[1] += nodepos[int(n)][1]
            accPos[2] += nodepos[int(n)][2]
            thiscolor = nodecol[int(n)]
        pos[0] = accPos[0] / len(label["group"])
        pos[1] = accPos[1] / len(label["group"])
        pos[2] = accPos[2] / len(label["group"])
        #nodelist["labels"].append(thislabel)
        print(label)

        nodelistIn.append(label)
        nodepos.append(pos)
        nodecol.append([255,0,0,255])
        


    #try:
    for count in range(0,len(nodepos)):
         #print(row[7])
        my_list = [nodelistIn[count]["name"],nodelistIn[count]["id"]]
        attrlist['names'].append(my_list)
        thisNodePos=[0,0,0]
        thisnode = {}
        thisnode["id"] = i
        thisnode["n"] = nodelistIn[count]["name"]
        thisnode["attrlist"] = my_list
        nodelist["nodes"].append(thisnode)
        
        x = int(float(nodepos[count][0])*65280)
        y = int(float(nodepos[count][1])*65280)
        z = int(float(nodepos[count][2])*65280)
        r = int(nodecol[count][0])
        g = int(nodecol[count][1])
        b = int(nodecol[count][2])
        a = int(nodecol[count][3])
        xh = int(x / 255)
        yh = int(y / 255)
        zh = int(z / 255)
        xl = x % 255
        yl = y % 255
        zl = z % 255
        pixelh = (xh,yh,zh)
        pixell = (xl,yl,zl)
        pixelc = (r,g,b,a)

        texh[count] = pixelh
        texl[count] = pixell
        texc[count] = pixelc

      
        #nodepos.append([float(row[0]),float(row[1]),float(row[2])])
        #nodecol.append([float(row[3]),float(row[4]),float(row[5]),100])
        #print(row)
         


    
    '''
    for label in labellist:
        #print(row)
        thiscolor = [200,200,200]
        thisnode = {}
         
        thisnode["id"] = l
        thisnode["group"] = label["group"]
        pos = [0,0,0]
        
        for n in label["group"]:
        #if ";" in row[0]:
        # A LIST OF NODES
            #my_list = row[0].split(";")
            #row[0] = my_list[1]
            #print(my_list)
            accPos = [0,0,0]

            

            accPos[0] += nodepos[int(n)][0]
            accPos[1] += nodepos[int(n)][1]
            accPos[2] += nodepos[int(n)][2]
            thiscolor = nodecol[int(n)]

        pos[0] = accPos[0] / len(label["group"])
        pos[1] = accPos[1] / len(label["group"])
        pos[2] = accPos[2] / len(label["group"])

        #nodelist["labels"].append(thislabel)
        #nodelist["nodes"].append(thisnode)
            #print(accPos)    
        x = int(float(pos[0])*65280)
        y = int(float(pos[1])*65280)
        z = int(float(pos[2])*65280)
        r = int(thiscolor[0])
        g = int(thiscolor[1])
        b = int(thiscolor[2])
        a = 127
        xh = int(x / 255)
        yh = int(y / 255)
        zh = int(z / 255)
        xl = x % 255
        yl = y % 255
        zl = z % 255
        pixelh = (xh,yh,zh)
        pixell = (xl,yl,zl)
        pixelc = (r,g,b,a)
        texh[i+l] = pixelh
        texl[i+l] = pixell
        texc[i+l] = pixelc

        #attrlist['names'].append([thisnode["n"],"label",])
        nodelist["nodes"].append(thisnode)
        
        l += 1
            #print(my_list)
    '''
    new_imgh.putdata(texh)
    new_imgl.putdata(texl)
    new_imgc.putdata(texc)
        
    pathXYZ = path + '/layouts/' +  name + 'XYZ.bmp'
    pathXYZl = path + '/layoutsl/' +  name + 'XYZl.bmp' 
    pathRGB = path + '/layoutsRGB/' +  name +  'RGB.png'


    new_imgh.save(pathXYZ)
    new_imgl.save(pathXYZl)
    new_imgc.save(pathRGB, "PNG")
    print("saved to "+ pathXYZ)


       

    with open(path + '/nodes.json', 'w') as outfile:
        json.dump(nodelist, outfile)



    #with open(path + '/names.json', 'w') as outfile:
        #json.dump(attrlist, outfile)


