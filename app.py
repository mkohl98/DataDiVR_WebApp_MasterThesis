import base64
import csv
import json
import logging
import os
import os.path

# import preview as pre
import random
import wave
from base64 import b64encode
from cgi import print_arguments
from io import StringIO
from mimetypes import guess_extension
from os import path

import flask
import numpy as np
import requests

# from flask_session import Session
from engineio.payload import Payload
from flask import (
    Flask,
    abort,
    current_app,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_socketio import SocketIO, emit, join_room, leave_room
from PIL import Image, ImageColor
from werkzeug.utils import secure_filename

import analytics
import annotation
import cartographs_func as CG
import chat
import chatGPTTest
import GlobalData as GD
import layout_module
import load_extensions
import plotlyExamples as PE
import search

# load audio and pad/trim it to fit 30 seconds
import TextToSpeech
import uploader
import uploaderGraph
import util
import websocket_functions as webfunc

log = logging.getLogger("werkzeug")
log.setLevel(logging.ERROR)

Payload.max_decode_packets = 50

app = Flask(__name__)
app.debug = False
app.config["SECRET_KEY"] = "secret"
app.config["SESSION_TYPE"] = "filesystem"

socketio = SocketIO(app, manage_session=False)
app, extensions = load_extensions.load(app)

### HTML ROUTES ###
sockets = [];

### Execute code before first request ###
@app.before_first_request
def execute_before_first_request():
    uploader.check_ProjectFolder()
    util.create_dynamic_links(app)
    GD.loadGD()
    GD.loadPFile()
    GD.loadPD()
    GD.loadColor()
    GD.loadLinks()
    GD.load_annotations()


@app.route("/")
def index():
    return flask.redirect("/home")


@app.route("/preview")
def preview():
    GD.loadGD()
    return render_template("preview.html", extensions=extensions)


@app.route("/main", methods=["GET"])
def main():
    username = util.generate_username()
    project = GD.data["actPro"]  # flask.request.args.get("project")
    if project is None:
        project = GD.data["actPro"]
        return "no project selected in GD.json"

    if flask.request.method == "GET":
        room = 1
        # Store the data in session
        flask.session["username"] = username
        flask.session["room"] = room
        # prolist = uploader.listProjects()

        return render_template("main.html", user=username, extensions=extensions)
    else:
        return "error"
    

'''


@app.route("/updateProject", methods=["GET"])
def updateProject():

    
    socketio.emit('ex',{'usr': 'l5jfcAUB8m', 'id': 'cbaddNode', 'fn': 'addNode', 'val': 'init'})
    return "updateproject"
     
'''






@app.route("/GPT", methods=["POST"])
def GPT():
    result = {}
    if request.method == "POST":
        data = flask.request.get_json()
        answer = chatGPTTest.GPTrequest(data.get("text"))
        fname = TextToSpeech.makeogg(answer, 0)
        print(answer)
        return {"text": answer, "audiofile": fname + ".ogg"}


@app.route("/TTS", methods=["POST", "GET"])
def TTS():
    result = {}
    if request.method == "GET":
        text = flask.request.args.get("text")
        voice = int(flask.request.args.get("voice"))
        result["text"] = TextToSpeech.makeogg(text, voice)
    return result


@app.route("/nodepanel", methods=["GET"])
def nodepanel():
    data = []
    return render_template("nodepanel.html", data)


@app.route("/uploadOLD", methods=["GET"])
def upload():
    prolist = GD.listProjects()
    return render_template(
        "upload.html",
        namespaces=prolist,
        extensions=extensions,
        sessionData=json.dumps(GD.data),
    )


@app.route("/upload", methods=["GET"])
def uploadNew():
    prolist = GD.listProjects()
    return render_template(
        "uploadNew.html",
        namespaces=prolist,
        extensions=extensions,
        sessionData=json.dumps(GD.data),
    )


@app.route("/uploadJSON", methods=["GET"])
def uploadJSON():
    prolist = GD.listProjects()
    return render_template(
        "uploadGRAPH.html",
        namespaces=prolist,
        extensions=extensions,
        sessionData=json.dumps(GD.data),
    )


@app.route("/uploadfiles", methods=["GET", "POST"])
def upload_files():
    return uploader.upload_files(flask.request)


@app.route("/uploadfilesNew", methods=["GET", "POST"])
def upload_filesNew():
    return uploader.upload_filesNew(flask.request)


@app.route("/uploadfilesJSON", methods=["GET", "POST"])
def upload_filesJSON():
    return uploaderGraph.upload_filesJSON(flask.request)


@app.route("/delpro", methods=["GET", "POST"])
def delete_project():
    return util.delete_project(flask.request)


# gets information about a specific node (project must be provided as argument)
@app.route("/node", methods=["GET", "POST"])
def nodeinfo():
    id = flask.request.args.get("id")
    key = flask.request.args.get("key")
    name = "static/projects/" + str(flask.request.args.get("project")) + "/nodes"
    nodestxt = open(name + ".json", "r")
    nodes = json.load(nodestxt)
    nlength = len(nodes["nodes"]) - len(nodes["labels"])
    print(nlength)
    if key:
        return str(nodes["nodes"][int(id)].get(key))
    else:
        if int(id) > nlength:
            # is label
            print(nodes["labels"][int(id) - nlength])
        return nodes["nodes"][int(id)]


@app.route("/home")
def home():
    if not flask.session.get("username"):
        flask.session["username"] = util.generate_username()
        flask.session["room"] = 1
    return render_template("home.html", sessionData=json.dumps(GD.data))


### DATA ROUTES###


@app.route("/load_all_projects", methods=["GET", "POST"])
def loadAllProjectsR():
    return jsonify(projects=GD.listProjects())


@app.route("/load_project/<name>", methods=["GET", "POST"])
def loadProjectInfoR(name):
    return uploader.loadProjectInfo(name)


@app.route("/projectAnnotations/<name>", methods=["GET"])
def loadProjectAnnotations(name):
    return uploader.loadAnnotations(name)



























###SocketIO ROUTES###


@socketio.on("join", namespace="/main")
def join(message):
    room = flask.session.get("room")
    join_room(room)
    print(message["usr"])
    
    print(
        webfunc.bcolors.WARNING
        + message["usr"]
        + " has entered the room."
        + webfunc.bcolors.ENDC
    )
    emit("status", {"usr": message["usr"], "msg": " has entered the room."}, room=room)


@socketio.on("ex", namespace="/main")
def ex(message):
    '''sends a socket signal'''
    room = flask.session.get("room")
    # print(webfunc.bcolors.WARNING+ flask.session.get("username")+ "ex: "+ json.dumps(message)+ webfunc.bcolors.ENDC)
    # message["usr"] = flask.session.get("username")

    print("incoming " + str(message) + "room=" + str(room))
    
    if message["fn"] == "refresh":
        folder = 'static/projects/' + GD.data["actPro"] + '/'
        pfile = {}
        with open(folder + 'pfile.json', 'r') as json_file:
            pfile = json.load(json_file)
        json_file.close()
        response = {"usr":"COYGnH6uOf","fn":"project","val":pfile}
        print("refresh      " +str(response))
        emit("ex", response, room=1)


    if message["fn"] == "sel":
        if (
            not message["id"] in GD.pdata.keys()
        ):  # check if selection exists in pdata.json
            GD.pdata[message["id"]] = ""
        GD.pdata[message["id"]] = message["opt"]
        GD.savePD()

    if message["id"] == "protLoad":
        response = {}
        response["usr"] = message["usr"]
        response["id"] = message["id"]
        response["fn"] = "loadProtein"
        response["val"] = GD.pdata["protnamedown"], GD.pdata["protstyle"]
        emit("ex", response, room=room)  # send to all clients

    if message["id"] == "search":
        if len(message["val"]) > 1:
            x = '{"id": "search", "val":[], "fn": "makeNodeButton", "parent":"scrollbox2"}'
            results = json.loads(x)
            results["val"] = search.search(message["val"])
            emit("ex", results, room=room)

    # Chat text message
    if message["fn"] == "chatmessage":
        response = {}
        response = message
        # print("C_DEBUG: in app if chatmessage", response)
        emit("ex", response, room=room)

    elif message["id"] == "nl":
        message["names"] = []
        message["fn"] = "cnl"
        message["prot"] = []
        message["protsize"] = []
        for id in message["data"]:
            message["names"].append(GD.nodes["nodes"][id]["n"])

        emit("ex", message, room=room)
        # print(message)

    # CLIPBOARD
    # TODO: dont save the colors to file but retrieve them from selected color texture
    elif message["id"] == "cbaddNode":
        if not "cbnode" in GD.pdata.keys():  # check if selection exists in pdata.json
            GD.pdata["cbnode"] = []
        if message["val"] != "init":  # used for initialization for newly joined client
            # if not, create it
            exists = False  # check if node already exists in selection
            for n in GD.pdata["cbnode"]:
                if int(n["id"]) == int(GD.pdata["activeNode"]):
                    exists = True
            if not exists:  # if not, add it
                cbnode = {}
                try:  ### improve this, runs sometimes into issues when activeNode is not valid
                    cbnode["id"] = int(GD.pdata["activeNode"])
                    cbnode["color"] = GD.pixel_valuesc[int(GD.pdata["activeNode"])]
                    cbnode["name"] = GD.nodes["nodes"][int(GD.pdata["activeNode"])]["n"]
                    GD.pdata["cbnode"].append(cbnode)
                    GD.savePD()
                except:
                    print("Select node to copy to clipboard.")
            else:
                print("already in selection")

        response = {}
        response["usr"] = message["usr"]
        response["id"] = message["id"]
        response["fn"] = "cbaddNode"
        response["val"] = GD.pdata["cbnode"]

        emit("ex", response, room=room)  # send to all clients

    elif message["fn"] == "colorbox":
        if message["id"] == "cbColorInput":
            # copy active color texture
            im1 = Image.open(
                "static/projects/"
                + GD.data["actPro"]
                + "/layoutsRGB/"
                + GD.pfile["layoutsRGB"][int(GD.pdata["layoutsRGBDD"])]
                + ".png",
                "r",
            )
            im2 = im1.copy()
            # convert rgb to hex string
            color = (
                int(message["r"]),
                int(message["g"]),
                int(message["b"]),
                int(message["a"] * 255),
            )
            pix_val = list(im1.getdata())

            # colorize clipboard selection
            for n in GD.pdata["cbnode"]:
                id = int(n["id"])
                pix_val[id] = color
            im2.putdata(pix_val)

            # save temp texture

            path = "static/projects/" + GD.data["actPro"] + "/layoutsRGB/temp1.png"
            im2.save(path)
            im1.close()
            im2.close()
            # send update signal to clients

            response = {}
            response["usr"] = message["usr"]
            response["fn"] = "updateTempTex"
            response["textures"] = []
            response["textures"].append(
                {
                    "channel": "nodeRGB",
                    "path": "static/projects/"
                    + GD.data["actPro"]
                    + "/layoutsRGB/temp1.png",
                }
            )

            emit("ex", response, room=room)
        emit("ex", message, room=room)

    elif message["fn"] == "selections":
        if message["id"] == "selectionsCb":
            activeSelIndex = int(GD.pdata["selectionsDD"])
            selectionNodes = GD.pfile["selections"][activeSelIndex]["nodes"]

            if not "cbnode" in GD.pdata.keys():
                GD.pdata["cbnode"] = []

            exists = False  # check if node already exists in clipboard
            for nodeID in selectionNodes:
                if int(nodeID) == int(GD.pdata["activeNode"]):
                    exists = True
                if not exists: 
                    cbnode = {}
                    try:  ### improve this, runs sometimes into issues when activeNode is not valid
                        cbnode["id"] = int(nodeID)
                        cbnode["color"] = GD.pixel_valuesc[int(nodeID)]
                        cbnode["name"] = GD.nodes["nodes"][int(nodeID)]["n"]
                        GD.pdata["cbnode"].append(cbnode)
                        GD.savePD()
                    except:
                        print("Select node to copy to clipboard.")

            response = {}
            response["usr"] = message["usr"]
            response["id"] = message["id"]
            response["fn"] = "cbaddNode"
            response["val"] = GD.pdata["cbnode"]
            emit("ex", response, room=room)


    elif message["fn"] == "clipboard": 
        if message["id"] == "cbClear":
            # clear in backend
            GD.pdata["cbnode"] = []
            GD.savePD()
            # tell frontend to remove all buttons
            response = {}
            response["usr"] = message["usr"]
            response["id"] = message["id"]
            response["fn"] = "cbaddNode"
            response["val"] = GD.pdata["cbnode"]
            emit("ex", response, room=room)
    

    elif message["fn"] == "layout":
        if message["id"] == "layoutInit":
            if message["val"] != "init":
                return
            # session data initialisation
            check_log = layout_module.init_client_display_log()
            # check if selected layout type already exists in session_data to handle button display
            # use sel from global data on drop down and use it as key to store and check for layout results
            check_existing_layout = layout_module.init_client_layout_exists()

            response = {}
            response["usr"] = message["usr"]
            response["id"] = message["id"]
            response["fn"] = "layout"
            response["val"] = {
                "showLog": check_log,
                "selectedLayoutGenerated": check_existing_layout,
            }
            emit("ex", response, room=room)

        # handle log display
        if message["id"] == "layoutLogShow":
            layout_module.show_log()
            response = {}
            response["usr"] = message["usr"]
            response["id"] = "showLog"
            response["fn"] = "layout"
            response["val"] = True
            emit("ex", response, room=room)

        if message["id"] == "layoutLogHide":
            layout_module.show_log()
            response = {}
            response["usr"] = message["usr"]
            response["id"] = "showLog"
            response["fn"] = "layout"
            response["val"] = False
            emit("ex", response, room=room)

        # layout algorithms
        if message["id"] == "layoutRandomApply":
            layout_id = layout_module.LAYOUT_IDS[0]  # 0 -> random layout

            # write log starting
            response_log = {}
            response_log["usr"] = message["usr"]
            response_log["id"] = "addLog"
            response_log["fn"] = "layout"
            response_log["log"] = {
                "type": "log",
                "msg": "Random layout generation running ...",
            }
            emit("ex", response_log, room=room)

            # retreive data and get layout positions
            if layout_id not in GD.session_data["layout"]["results"].keys():
                if "graph" not in GD.session_data.keys():
                    GD.session_data["graph"] = util.project_to_graph(GD.data["actPro"])
                graph = GD.session_data["graph"]
                result_obj = layout_module.layout_random(ordered_graph=graph)
                if result_obj["success"] is False:
                    print("ERROR: ", result_obj["error"])
                    response_log["log"] = result_obj["log"]
                    emit("ex", response_log, room=room)
                    return

                GD.session_data["layout"]["results"][layout_id] = result_obj["content"]

            # generate layout textures
            positions = GD.session_data["layout"]["results"][layout_id]
            result_obj = layout_module.pos_to_textures(positions)
            if result_obj["success"] is False:
                print("ERROR: ", result_obj["error"])

                response_log["log"] = result_obj["log"]
                emit("ex", response_log, room=room)
                return

            # write log finish
            response_log["log"] = {
                "type": "log",
                "msg": "Generated random layout successfully.",
            }
            emit("ex", response_log, room=room)

            # display rerun and save buttons
            response_layout_exists = {}
            response_layout_exists["usr"] = message["usr"]
            response_layout_exists["fn"] = "layout"
            response_layout_exists["id"] = "layoutExists"
            response_layout_exists["val"] = layout_module.check_layout_exists()
            emit("ex", response_layout_exists, room=room)

            # update temp layout
            response = {}
            response["usr"] = message["usr"]
            response["fn"] = "updateTempTex"
            response["textures"] = result_obj["textures"]
            emit("ex", response, room=room)
            return

        if message["id"] == "layoutEigenApply":
            layout_id = layout_module.LAYOUT_IDS[1]  # 1 -> eigen layout

            # write log starting
            response_log = {}
            response_log["usr"] = message["usr"]
            response_log["id"] = "addLog"
            response_log["fn"] = "layout"
            response_log["log"] = {
                "type": "log",
                "msg": "Eigenlayout generation running ...",
            }
            emit("ex", response_log, room=room)

            # retreive data and get layout positions
            if layout_id not in GD.session_data["layout"]["results"].keys():
                if "graph" not in GD.session_data.keys():
                    GD.session_data["graph"] = util.project_to_graph(GD.data["actPro"])
                graph = GD.session_data["graph"]
                result_obj = layout_module.layout_eigen(ordered_graph=graph)
                if result_obj["success"] is False:
                    print("ERROR: ", result_obj["error"])
                    response_log["log"] = result_obj["log"]
                    emit("ex", response_log, room=room)
                    return

                GD.session_data["layout"]["results"][layout_id] = result_obj["content"]

            # generate layout textures
            positions = GD.session_data["layout"]["results"][layout_id]
            result_obj = layout_module.pos_to_textures(positions)
            if result_obj["success"] is False:
                print("ERROR: ", result_obj["error"])

                response_log["log"] = result_obj["log"]
                emit("ex", response_log, room=room)
                return

            # write log finish
            response_log["log"] = {
                "type": "log",
                "msg": "Generated Eigenlayout successfully.",
            }
            emit("ex", response_log, room=room)

            # display rerun and save buttons
            response_layout_exists = {}
            response_layout_exists["usr"] = message["usr"]
            response_layout_exists["fn"] = "layout"
            response_layout_exists["id"] = "layoutExists"
            response_layout_exists["val"] = layout_module.check_layout_exists()
            emit("ex", response_layout_exists, room=room)

            # update temp layout
            response = {}
            response["usr"] = message["usr"]
            response["fn"] = "updateTempTex"
            response["textures"] = result_obj["textures"]
            emit("ex", response, room=room)
            return

        if message["id"] == "layoutCartoLocalApply":
            layout_id = layout_module.LAYOUT_IDS[2]  # 2 -> local layout

            # write log starting
            response_log = {}
            response_log["usr"] = message["usr"]
            response_log["id"] = "addLog"
            response_log["fn"] = "layout"
            response_log["log"] = {
                "type": "log",
                "msg": "cartoGRAPHS Local layout generation running ...",
            }
            emit("ex", response_log, room=room)

            # retreive data and get layout positions
            if layout_id not in GD.session_data["layout"]["results"].keys():
                if "graph" not in GD.session_data.keys():
                    GD.session_data["graph"] = util.project_to_graph(GD.data["actPro"])
                graph = GD.session_data["graph"]
                result_obj = layout_module.layout_carto_local(ordered_graph=graph)
                if result_obj["success"] is False:
                    print("ERROR: ", result_obj["error"])
                    response_log["log"] = result_obj["log"]
                    emit("ex", response_log, room=room)
                    return

                GD.session_data["layout"]["results"][layout_id] = result_obj["content"]

            # generate layout textures
            positions = GD.session_data["layout"]["results"][layout_id]
            result_obj = layout_module.pos_to_textures(positions)
            if result_obj["success"] is False:
                print("ERROR: ", result_obj["error"])

                response_log["log"] = result_obj["log"]
                emit("ex", response_log, room=room)
                return

            # write log finish
            response_log["log"] = {
                "type": "log",
                "msg": "Generated cartoGRAPHS Local layout successfully.",
            }
            emit("ex", response_log, room=room)

            # display rerun and save buttons
            response_layout_exists = {}
            response_layout_exists["usr"] = message["usr"]
            response_layout_exists["fn"] = "layout"
            response_layout_exists["id"] = "layoutExists"
            response_layout_exists["val"] = layout_module.check_layout_exists()
            emit("ex", response_layout_exists, room=room)

            # update temp layout
            response = {}
            response["usr"] = message["usr"]
            response["fn"] = "updateTempTex"
            response["textures"] = result_obj["textures"]
            emit("ex", response, room=room)
            return

        if message["id"] == "layoutCartoGlobalApply":
            layout_id = layout_module.LAYOUT_IDS[3]  # 3 -> global layout

            # write log starting
            response_log = {}
            response_log["usr"] = message["usr"]
            response_log["id"] = "addLog"
            response_log["fn"] = "layout"
            response_log["log"] = {
                "type": "log",
                "msg": "cartoGRAPHS Global layout generation running ...",
            }
            emit("ex", response_log, room=room)

            # retreive data and get layout positions
            if layout_id not in GD.session_data["layout"]["results"].keys():
                if "graph" not in GD.session_data.keys():
                    GD.session_data["graph"] = util.project_to_graph(GD.data["actPro"])
                graph = GD.session_data["graph"]
                result_obj = layout_module.layout_carto_global(ordered_graph=graph)
                if result_obj["success"] is False:
                    print("ERROR: ", result_obj["error"])
                    response_log["log"] = result_obj["log"]
                    emit("ex", response_log, room=room)
                    return

                GD.session_data["layout"]["results"][layout_id] = result_obj["content"]

            # generate layout textures
            positions = GD.session_data["layout"]["results"][layout_id]
            result_obj = layout_module.pos_to_textures(positions)
            if result_obj["success"] is False:
                print("ERROR: ", result_obj["error"])

                response_log["log"] = result_obj["log"]
                emit("ex", response_log, room=room)
                return

            # write log finish
            response_log["log"] = {
                "type": "log",
                "msg": "Generated cartoGRAPHS Global layout successfully.",
            }
            emit("ex", response_log, room=room)

            # display rerun and save buttons
            response_layout_exists = {}
            response_layout_exists["usr"] = message["usr"]
            response_layout_exists["fn"] = "layout"
            response_layout_exists["id"] = "layoutExists"
            response_layout_exists["val"] = layout_module.check_layout_exists()
            emit("ex", response_layout_exists, room=room)

            # update temp layout
            response = {}
            response["usr"] = message["usr"]
            response["fn"] = "updateTempTex"
            response["textures"] = result_obj["textures"]
            emit("ex", response, room=room)
            return

        if message["id"] == "layoutCartoImportanceApply":
            layout_id = layout_module.LAYOUT_IDS[4]  # 4 -> importance layout

            # write log starting
            response_log = {}
            response_log["usr"] = message["usr"]
            response_log["id"] = "addLog"
            response_log["fn"] = "layout"
            response_log["log"] = {
                "type": "log",
                "msg": "cartoGRAPHS Importance layout generation running ...",
            }
            emit("ex", response_log, room=room)

            # retreive data and get layout positions
            if layout_id not in GD.session_data["layout"]["results"].keys():
                if "graph" not in GD.session_data.keys():
                    GD.session_data["graph"] = util.project_to_graph(GD.data["actPro"])
                graph = GD.session_data["graph"]
                result_obj = layout_module.layout_carto_importance(ordered_graph=graph)
                if result_obj["success"] is False:
                    print("ERROR: ", result_obj["error"])
                    response_log["log"] = result_obj["log"]
                    emit("ex", response_log, room=room)
                    return

                GD.session_data["layout"]["results"][layout_id] = result_obj["content"]

            # generate layout textures
            positions = GD.session_data["layout"]["results"][layout_id]
            result_obj = layout_module.pos_to_textures(positions)
            if result_obj["success"] is False:
                print("ERROR: ", result_obj["error"])

                response_log["log"] = result_obj["log"]
                emit("ex", response_log, room=room)
                return

            # write log finish
            response_log["log"] = {
                "type": "log",
                "msg": "Generated cartoGRAPHS Importance layout successfully.",
            }
            emit("ex", response_log, room=room)

            # display rerun and save buttons
            response_layout_exists = {}
            response_layout_exists["usr"] = message["usr"]
            response_layout_exists["fn"] = "layout"
            response_layout_exists["id"] = "layoutExists"
            response_layout_exists["val"] = layout_module.check_layout_exists()
            emit("ex", response_layout_exists, room=room)

            # update temp layout
            response = {}
            response["usr"] = message["usr"]
            response["fn"] = "updateTempTex"
            response["textures"] = result_obj["textures"]
            emit("ex", response, room=room)
            return

        if message["id"] == "layoutSpectralApply":
            layout_id = layout_module.LAYOUT_IDS[5]  # 5 -> random layout

            # write log starting
            response_log = {}
            response_log["usr"] = message["usr"]
            response_log["id"] = "addLog"
            response_log["fn"] = "layout"
            response_log["log"] = {
                "type": "log",
                "msg": "Spectral layout generation running ...",
            }
            emit("ex", response_log, room=room)

            # retreive data and get layout positions
            if layout_id not in GD.session_data["layout"]["results"].keys():
                if "graph" not in GD.session_data.keys():
                    GD.session_data["graph"] = util.project_to_graph(GD.data["actPro"])
                graph = GD.session_data["graph"]
                result_obj = layout_module.layout_spectral(ordered_graph=graph)
                if result_obj["success"] is False:
                    print("ERROR: ", result_obj["error"])
                    response_log["log"] = result_obj["log"]
                    emit("ex", response_log, room=room)
                    return

                GD.session_data["layout"]["results"][layout_id] = result_obj["content"]

            # generate layout textures
            positions = GD.session_data["layout"]["results"][layout_id]
            result_obj = layout_module.pos_to_textures(positions)
            if result_obj["success"] is False:
                print("ERROR: ", result_obj["error"])

                response_log["log"] = result_obj["log"]
                emit("ex", response_log, room=room)
                return

            # write log finish
            response_log["log"] = {
                "type": "log",
                "msg": "Generated spectral layout successfully.",
            }
            emit("ex", response_log, room=room)

            # display rerun and save buttons
            response_layout_exists = {}
            response_layout_exists["usr"] = message["usr"]
            response_layout_exists["fn"] = "layout"
            response_layout_exists["id"] = "layoutExists"
            response_layout_exists["val"] = layout_module.check_layout_exists()
            emit("ex", response_layout_exists, room=room)

            # update temp layout
            response = {}
            response["usr"] = message["usr"]
            response["fn"] = "updateTempTex"
            response["textures"] = result_obj["textures"]
            emit("ex", response, room=room)
            return


    elif message["fn"] == "module":
        module_id = message["id"]
        response = {}
        response["usr"] = message["usr"]
        response["id"] = message["id"]
        response["fn"] = "moduleState"

        # False = minimized, True = maximized

        if message["val"] == "init":
            module_id = message["id"]
            if module_id not in GD.pdata.keys():
                GD.pdata[module_id] = False
                GD.savePD()
            response["val"] = GD.pdata[module_id]
            emit("ex", response, room=room)

        if message["val"] == "maximize":
            GD.pdata[module_id] = True
            GD.savePD()
            response["val"] = True
            emit("ex", response, room=room)

        if message["val"] == "minimize":
            GD.pdata[module_id] = False
            GD.savePD()
            response["val"] = False
            emit("ex", response, room=room)


    elif message["fn"] == "dropdown":
        response = {}
        response["usr"] = message["usr"]
        response["id"] = message["id"]
        response["fn"] = "dropdown"
        response["parent"] = message["id"]

        if "val" in message.keys():
            # init message called when socket connection is established
            if message["val"] == "init":
                # C A R T O G R A P H S
                # dropdown for layout type selection
                layout_selected = 0
                if message["id"] == "CGlayouts":
                    response["opt"] = [
                        "Local layout",
                        "Global layout",
                        "Importance layout",
                    ]
                    response["sel"] = layout_selected

                # dropdown for fixed selections
                if message["id"] == "analytics":
                    response["opt"] = analytics.ANALYTICS_TABS
                    response["sel"] = "0"

                if message["id"] == "layoutModule":
                    response["opt"] = layout_module.LAYOUT_TABS
                    response["sel"] = "0"

                # dropdown for visualization type selection
                vis_selected = 0
                if message["id"] == "CGvis":
                    response["opt"] = [
                        "2D Portrait",
                        "3D Portrait",
                        "Topographic",
                        "Geodesic",
                    ]
                    response["sel"] = vis_selected

                elif message["id"] == "projDD":
                    response["opt"] = GD.plist
                    response["sel"] = GD.plist.index(GD.data["actPro"])

                    response2 = {}
                    response2["usr"] = message["usr"]
                    if not "nodecount" in GD.pfile:
                        GD.pfile["nodecount"] = len(GD.nodes["nodes"])
                        GD.pfile["labelcount"] = 0
                        GD.pfile["linkcount"] = len(GD.links["links"])
                        GD.savePFile()

                    response2["val"] = GD.pfile
                    response2["fn"] = "project"
                    emit("ex", response2, room=room)
                else:
                    if message["id"] not in GD.pdata:
                        GD.pdata[message["id"]] = 0
                    response["sel"] = GD.pdata[message["id"]]
                    # assign data for options
                    if message["id"] == "layoutsDD":
                        response["opt"] = GD.pfile["layouts"]
                    elif message["id"] == "layoutsRGBDD":
                        response["opt"] = GD.pfile["layoutsRGB"]
                    elif message["id"] == "linksDD":
                        response["opt"] = GD.pfile["links"]
                    elif message["id"] == "linksRGBDD":
                        response["opt"] = GD.pfile["linksRGB"]
                    elif message["id"] == "selectionsDD":
                        options = []
                        for i in range(len(GD.pfile["selections"])):
                            options.append(GD.pfile["selections"][i]["name"])
                        response["opt"] = options
                        print(options)


                    if "opt" in response.keys():
                        # dirty fix that sel of pdata layoutsDD is somwhow always = 2
                        response["sel"] = str(min(len(response["opt"]) - 1, int(response["sel"])))



                # dropdown for annotations
                if message["id"] == "annotation-1":
                    response["opt"] = (
                        list(GD.annotations.keys())
                        if len(list(GD.annotations.keys())) > 0
                        else ["-"]
                    )
                    response["sel"] = (
                        0
                        if "annotation-1" not in GD.pdata.keys()
                        else GD.pdata["annotation-1"]
                    )
                if message["id"] == "annotation-2":
                    response["opt"] = (
                        list(GD.annotations.keys())
                        if len(list(GD.annotations.keys())) > 0
                        else ["-"]
                    )
                    response["sel"] = (
                        0
                        if "annotation-2" not in GD.pdata.keys()
                        else GD.pdata["annotation-2"]
                    )
                if message["id"] == "annotation-Operations":
                    response["opt"] = ["UNION", "INTERSECTION", "SUBTRACTION"]
                    response["sel"] = (
                        0
                        if "annotation-Operations" not in GD.pdata.keys()
                        else GD.pdata["annotation-Operations"]
                    )

            else:  # user input message
                # clear analytics container
                if message["id"] == "analytics":
                    # check if you actually switch
                    if message["val"] != GD.pdata["analytics"]:
                        response_clear = {}
                        response_clear["fn"] = "analytics"
                        response_clear["id"] = "clearAnalyticsContainer"
                        response_clear["usr"] = message["usr"]
                        emit("ex", response_clear, room=room)

                if message["id"] == "projDD":  # PROJECT CHANGE
                    GD.data["actPro"] = GD.plist[int(message["val"])]
                    GD.saveGD()
                    GD.loadGD()
                    GD.loadPFile()
                    GD.loadPD()
                    GD.loadColor()
                    GD.loadLinks()
                    GD.load_annotations()

                    response["sel"] = message["val"]
                    response["name"] = message["msg"]
                    print("changed Project to " + str(GD.plist[int(message["val"])]))

                    response2 = {}
                    response2["usr"] = message["usr"]
                    response2["val"] = GD.pfile
                    response2["fn"] = "project"
                    emit("ex", response2, room=room)

                    # display rerun and save buttons for layout module
                    emit(
                        "ex",
                        {
                            "usr": message["usr"],
                            "fn": "layout",
                            "id": "layoutExists",
                            "val": False,
                        },
                        room=room,
                    )
                    # update not self updating elements
                    emit("ex", {"fn": "annotationDD", "id": "initDD", "options": GD.annotation_types})
                else:
                    response["sel"] = message["val"]
                    response["name"] = message["msg"]
                    if message["id"] not in GD.pdata:
                        GD.pdata[message["id"]] = ""
                        print("newGD Variable created")

                    GD.pdata[message["id"]] = message["val"]
                    GD.savePD()

                if message["id"] == "selectionsDD":
                    print(GD.pfile["selections"][int(message["val"])]["nodes"])
                    response2 = {}
                    response2["usr"] = message["usr"]
                    response2["id"] = message["id"]
                    response2["parent"] = "scrollbox1"
                    response2["fn"] = "makeNodeButton"
                    response2["val"] = []
                    ids = GD.pfile["selections"][int(message["val"])]["nodes"]
                    for d in ids:
                        node = {}
                        node["name"] = GD.nodes["nodes"][int(d)]["n"]
                        node["color"] = GD.pixel_valuesc[int(d)]
                        node["id"] = d
                        response2["val"].append(node)
                    emit("ex", response2, room=room)

                if message["id"] == "layoutModule":
                    # check for layout switch
                    # display rerun and save buttons
                    response_layout_exists = {}
                    response_layout_exists["usr"] = message["usr"]
                    response_layout_exists["fn"] = "layout"
                    response_layout_exists["id"] = "layoutExists"
                    response_layout_exists["val"] = layout_module.check_layout_exists()
                    emit("ex", response_layout_exists, room=room)
        emit("ex", response, room=room)
        print(response)

    # EXPERIMENTAL dynamic svg creation with matplotlib
    elif message["fn"] == "showSVG":
        emit("ex", PE.matplotsvg(message), room=room)

    # EXPERIMENTAL saving html file to disk
    elif message["fn"] == "showPlotly":
        emit("ex", PE.writeHtml(), room=room)

    elif message["fn"] == "Plotly2js":
        response = {}
        response["fn"] = "plotly2js"
        response["parent"] = message["parent"]  # target <div>

        if message["msg"] == "Graph":
            response["val"] = PE.networkGraph()
            emit("ex", response, room=room)
        elif message["msg"] == "Barchart":
            response["val"] = PE.connectionBarGraph()
            emit("ex", response, room=room)
        elif message["msg"] == "timeGraph":
            response["val"] = PE.timeGraph()
            emit("ex", response, room=room)
        elif message["msg"] == "scatterGraph":
            response["val"] = PE.scatterGraph()
            emit("ex", response, room=room)

        # Draw Cartographs
        elif message["msg"] == "draw graph":
            response["val"] = CG.cartoGraphs()
            emit("ex", response, room=room)

    elif message["fn"] == "submit_butt":
        if message["parent"] not in GD.pdata:
            GD.pdata[message["parent"]] = []
        if message["val"] != "init":
            GD.pdata[message["parent"]].append(message["val"])
            GD.savePD()
        response = {}
        response["fn"] = "serVarExample"
        response["parent"] = message["parent"]

        response["buttons"] = GD.pdata[message["parent"]]
        # print(response)
        emit("ex", response, room=room)

    elif message["fn"] == "sli":
        if message["id"] not in GD.pdata:
            GD.pdata[message["id"]] = ""
            print("newGD Variable created")
        if message["val"] != "init":
            GD.pdata[message["id"]] = message["val"]
            GD.savePD()
        response = {}
        response["usr"] = message["usr"]
        response["fn"] = "sli"
        response["id"] = message["id"]
        response["val"] = GD.pdata[message["id"]]
        print(response)
        emit("ex", response, room=room)

    elif message["fn"] == "node":
        response = {}

        response["val"] = {}
        response["fn"] = "node"
        response["id"] = message["val"]
        response["nch"] = len(GD.nchildren[int(message["val"])])
        response["val"] = GD.nodes["nodes"][int(message["val"])]
        GD.pdata["activeNode"] = message["val"]

        if "protein_info" in GD.nodes["nodes"][int(message["val"])]:
            if (
                not "protstyle" in GD.pdata.keys()
            ):  # check if selection exists in pdata.json
                GD.pdata["protstyle"] = ""
            GD.pdata["protstyle"] = list(
                GD.nodes["nodes"][int(message["val"])]["protein_info"][0].keys()
            )[1]

            if (
                not "protnamedown" in GD.pdata.keys()
            ):  # check if selection exists in pdata.json
                GD.pdata["protstyle"] = ""
            GD.pdata["protnamedown"] = GD.nodes["nodes"][int(message["val"])][
                "uniprot"
            ][0]

            GD.savePD()

        # print(response)
        emit("ex", response, room=room)

    elif message["fn"] == "children":
        response2 = {}
        response2["usr"] = message["usr"]
        response2["id"] = "children"
        response2["parent"] = "scrollbox3"
        response2["fn"] = "makeNodeButton"
        response2["nid"] = GD.nodes["nodes"][int(GD.pdata["activeNode"])]["n"]
        response2["val"] = []

        ids = GD.nchildren[int(GD.pdata["activeNode"])]
        for d in ids:
            node = {}
            node["name"] = GD.nodes["nodes"][int(d)]["n"]
            node["color"] = GD.pixel_valuesc[int(d)]
            node["id"] = d
            response2["val"].append(node)
        print(response2)
        emit("ex", response2, room=room)
    else:
        emit("ex", message, room=room)


@socketio.on("left", namespace="/main")
def left(message):
    room = flask.session.get("room")
    username = flask.session.get("username")
    leave_room(room)
    flask.session.clear()
    emit("status", {"msg": username + " has left the room."}, room=room)
    print(
        webfunc.bcolors.WARNING
        + flask.session.get("username")
        + " has left the room."
        + webfunc.bcolors.ENDC
    )
    util.construct_nav_bar(app)



if __name__ == "__main__":
    socketio.run(app , debug=True)
