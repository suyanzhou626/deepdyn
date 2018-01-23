import logging as logger
import math as mth

import networkx as nx
import numpy as np


class Lattice:
    def __init__(self, image_arr_2d):
        logger.basicConfig(level=logger.INFO)
        self.x_size, self.y_size = image_arr_2d.shape
        self.lattice = None
        self.accumulator = np.zeros([self.x_size, self.y_size], dtype=np.uint8)
        self.total_weight = 0.0

    @staticmethod
    def _connect_8(graph):
        for i, j in graph:
            n0 = (i, j)
            n1 = (i - 1, j + 1)
            n2 = (i + 1, j - 1)
            n3 = (i - 1, j - 1)
            n4 = (i + 1, j + 1)
            if n1 in graph.nodes():
                graph.add_edge(n0, n1)
            if n2 in graph.nodes():
                graph.add_edge(n0, n2)
            if n3 in graph.nodes():
                graph.add_edge(n0, n3)
            if n4 in graph.nodes():
                graph.add_edge(n0, n4)

    def generate_lattice_graph(self, eight_connected=False):
        if eight_connected:
            logger.info(msg='Creating 8-connected lattice.')
        else:
            logger.info(msg='Creating 4-connected lattice.')
        if self.lattice is not None:
            logger.warning(msg='Lattice already exists. Overriding..')
        self.lattice = nx.grid_2d_graph(self.x_size, self.y_size)

        if eight_connected:
            Lattice._connect_8(self.lattice)

    def assign_cost(self, images=[()], alpha=1, threshold=np.inf, override=False, log=False):
        i = 0
        edges_to_remove = []
        for n1 in self.lattice.nodes():
            for n2 in nx.neighbors(self.lattice, n1):
                if self.lattice[n1][n2] == {} or override:
                    cost = 0.0
                    for weight, arr in images:
                        i_diff = max(arr[n1[0], n1[1]], arr[n2[0], n2[1]])
                        cost += weight * mth.pow(mth.e, alpha * (i_diff / 255))
                    if cost <= threshold:
                        self.lattice[n1][n2]['cost'] = cost
                    else:
                        edges_to_remove.append((n1, n2))
            if log:
                print('\r' + str(i) + ': ' + str(n1), end='')
                i += 1

        # Remove edges that exceed the threshold
        self.lattice.remove_edges_from(edges_to_remove)

        # Remove isolated (i.e. zero-degree) nodes
        self.lattice.remove_nodes_from(list(nx.isolates(self.lattice)))