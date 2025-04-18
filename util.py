import colorsys
import json
import os
import random
import shutil
from collections import OrderedDict

import flask
import matplotlib.cm as cm
import networkx as nx
import pandas as pd

import GlobalData as GD
import uploader


def delete_project(request: flask.request):
    """
    Delete a project folder and all its contents.
    """
    project_name = request.args.get("project")
    projects = uploader.listProjects()
    if project_name is None:
        return f"Error: No project name provided. Example:\n<a href='{flask.request.base_url}?project={projects[0]}'>{flask.request.base_url}?project={projects[0]}</a>"

    project_path = os.path.join("static", "projects", project_name)
    if not os.path.exists(project_path):
        return f"<h4>Project {project_name} does not exist!</h4>"
    shutil.rmtree(project_path)
    return f"<h4>Project {project_name} deleted!</h4>"


def generate_username():
    """
    If no username is provided, generate a random one and return it
    """
    username = flask.request.args.get("usr")
    if username is None:
        username = str(random.randint(1001, 9998))
    else:
        username = username + str(random.randint(1001, 9998))
    return username


def has_no_empty_params(rule):
    """
    Filters the route to ignore route with empty params.
    """
    defaults = rule.defaults if rule.defaults is not None else ()
    arguments = rule.arguments if rule.arguments is not None else ()
    return len(defaults) >= len(arguments)


def get_all_links(app) -> list[list[str, str]]:
    """Extracts all routes from flask app and return a list of tuples of which the first value is the route and the seconds is the name of the corresponding python function."""
    links = []
    for rule in app.url_map.iter_rules():
        # Filter out rules we can't navigate to in a browser
        # and rules that require parameters
        if "GET" in rule.methods and has_no_empty_params(rule):
            url = flask.url_for(rule.endpoint, **(rule.defaults or {}))
            links.append((url, rule.endpoint))
    return links


def create_dynamic_links(app: flask.app.Flask):
    # Get all links from flask
    links = get_all_links(app)
    # links = [link for link in links if len(link[0].split("/"))>2]
    GD.data["url_map"] = links


def prepare_protein_structures(nodes):
    PREFIX = "AF-"
    SUFFIX = "-F1-model_"
    ALPHAFOLD_VER = "v2"
    nodes_data = nodes["nodes"]
    nodes_data = pd.DataFrame(nodes_data)
    if not "uniprot" in nodes_data.columns:
        return nodes

    csv_file = os.path.join(
        "static", "examplefiles", "protein_structure_info", "overview.csv"
    )
    protein_structure_infos = pd.read_csv(csv_file, index_col=0, header=0)
    protein_structure_infos = protein_structure_infos.dropna(how="all", axis=0)

    scale_columns = [
        c
        for c in protein_structure_infos.columns
        if c not in ["pdb_file", "multi_structure", "parts"]
    ]

    # Normalize scales to [0,1]
    protein_structure_infos[scale_columns] = protein_structure_infos[
        scale_columns
    ].apply(lambda c: c / c.max(), axis=0)

    def extract_node_info(
        uniprot_ids,
        protein_structure_infos=protein_structure_infos,
        scale_columns=scale_columns,
    ):
        info = []
        ids = [ident for ident in uniprot_ids if ident in protein_structure_infos.index]
        for ident in ids:
            structure_info = {}
            structure_info["file"] = PREFIX + ident + SUFFIX + ALPHAFOLD_VER
            for c in scale_columns:
                scale = protein_structure_infos.loc[ident, c]
                if pd.isna(scale):
                    continue
                structure_info[c] = scale
            info.append(structure_info)
        return info

    nodes_data["protein_info"] = None
    has_uniprot = nodes_data[nodes_data["uniprot"].notnull()].copy()
    has_uniprot["protein_info"] = has_uniprot["uniprot"].apply(extract_node_info)
    nodes_data.update(has_uniprot)
    nodes_data_filtered = [
        {k: v for k, v in row.items() if isinstance(v, list) or pd.notna(v)}
        for _, row in nodes_data.iterrows()
    ]
    # Convert the list of dictionaries to a JSON-like structure
    nodes = {"nodes": [data for data in nodes_data_filtered]}
    return nodes


def get_identifier_collection():
    tsv_file = os.path.join(
        "static", "examplefiles", "protein_structure_info", "uniprot_identifiers.tsv"
    )
    identifier_collection = pd.read_csv(tsv_file, sep="\t")


class OrderedGraph(nx.Graph):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.node_order = []  # List to store the order of node addition

    def add_node(self, node_for_adding, **attr):
        super().add_node(node_for_adding, **attr)
        self.node_order.append(node_for_adding)

    def add_nodes_from(self, nodes_for_adding, **attr):
        super().add_nodes_from(nodes_for_adding, **attr)
        self.node_order.extend(nodes_for_adding)


def project_to_graph(project):
    with open(f"./static/projects/{project}/links.json") as links_json:
        links = json.load(links_json)
    try:
        with open(f"./static/projects/{project}/nodes.json") as nodes_json:
            nodes = json.load(nodes_json)
    except FileNotFoundError:
        # here maybe names.json parsing (even if its deprecated)
        raise FileNotFoundError(
            "The selected Project does not support nodes.json file for storing nodes."
        )

    graph_dict = OrderedDict()

    for node in nodes["nodes"]:
        graph_dict[str(node["id"])] = []
    for link in links["links"]:
        graph_dict[str(link["s"])].append(str(link["e"]))

    graph = nx.from_dict_of_lists(graph_dict, create_using=OrderedGraph)
    return graph


def rgb_to_hex(color):
    if len(color) == 3:
        r, g, b = color
    if len(color) == 4:
        r, g, b, a = color
    return f"#{r:02x}{g:02x}{b:02x}"


def sample_color_gradient(plt_color_map, values):
    """
    colors has to be lists as color = [r, g, b]
    returns list of tuples according to the color
    """
    colors = []
    colormap = cm.get_cmap(plt_color_map)

    for value in values:
        # Interpolate between colors
        interpolated_color = colormap(value)
        rgb_color = tuple(int(x * 255) for x in interpolated_color[:3])
        colors.append(rgb_color)

    return colors


def generate_colors(n, s=None, v=None, alpha=None):
    # n: int, number of colors to generate
    # s: float [0.0, 1.0] Saturation
    # v: float [0.0, 1.0] Light value

    if s is None:
        s = random.uniform(0.7, 1.0)
    if v is None:
        v = random.uniform(0.7, 1.0)
    if alpha is None:
        alpha = 100

    if n <= 0:
        return []

    colors = []
    hue_increment = 1.0 / n

    for i in range(n):
        hue = i * hue_increment
        rgb = colorsys.hsv_to_rgb(hue, s, v)
        rgba_tuple = (int(rgb[0] * 255), int(rgb[1] * 255), int(rgb[2] * 255), alpha)
        colors.append(rgba_tuple)

    return colors
