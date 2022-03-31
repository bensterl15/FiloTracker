from random import randint
import numpy as np

import pyvista as pv
import mat73
from scipy.io import loadmat

from Model.constants_and_paths import MAX_PROTRUSIONS_INDEX


class Mesh:

    def __init__(self, path_mesh, path_segmentation, path_statistics, black_protrusions=False):
        # Load the segmentation:
        self.segmentation = self._load_segmentation(path_segmentation)
        # We mostly care about the unique segmentation
        self.segmentation_unique = np.unique(self.segmentation)

        # Load the mesh statistics:
        self.statistics = self.load_statistics(path_statistics)

        mesh_dict = mat73.loadmat(path_mesh)
        # Load numpy arrays of the vertices and faces:
        mesh_vertices = mesh_dict['surface']['vertices']
        mesh_faces = mesh_dict['surface']['faces']

        # Cast faces to int.. Subtract 1 to change from MATLAB 1-indexed:
        mesh_faces = mesh_faces.astype(int) - 1
        # We need to put 3's in front of each face to indicate it is a triangle:
        mesh_faces = np.hstack((3 * np.ones((mesh_faces.shape[0], 1), dtype=int), mesh_faces))

        # Will need these later:
        self.mesh_faces = mesh_faces
        self.mesh_vertices = mesh_vertices

        # Prepare base segmentation
        base_faces = mesh_faces[self.segmentation == 0]
        # Create a polydata to store the base cell:
        self.base_cell = pv.PolyData(mesh_vertices, base_faces)

        self.regions = []
        for i in range(1, self.segmentation_unique.shape[0]):
            region_faces = mesh_faces[self.segmentation == self.segmentation_unique[i]]
            # Create a polydata to store the base cell:
            region = pv.PolyData(mesh_vertices, region_faces)
            self.regions.append(region)

        # Generate black protrusions:
        if black_protrusions:
            self.protrusion_colors = np.zeros((self.segmentation_unique.shape[0], 3))
        # Generate ordered colors:
        else:
            # Weight the colors, because we do not want anything too close to black or white:
            self.protrusion_colors = np.random.uniform(size=(self.segmentation_unique.shape[0], 3)) * 0.3 + 0.3

        self.removed_protrusions = []

    # When the user saves after removal section, finalize the mesh:
    def removal_finalize(self):
        # Set all the segmentation indices we removed to zero:
        for i in range(self.segmentation.shape[0]):
            if self.segmentation[i] in self.removed_protrusions:
                self.segmentation[i] = 0

        # Gather the indices of the statistics we wish to remove:
        indices_to_remove = []
        # -1 because we do not count the base:
        for i in range(self.segmentation_unique.shape[0] - 1):
            if self.statistics['index'][i] in self.removed_protrusions:
                indices_to_remove.append(i)

        # Finally, remove all the entries that came from removed protrusions:
        for key in self.statistics:
            self.statistics[key] = np.delete(self.statistics[key], np.array(indices_to_remove), 0)

    # When the user saves progress of tracking, finalize the SECOND MESH ONLY:
    def tracking_finalize(self, previous_mesh, pairings, min_index):
        # First, change all protrusions to be unique:
        used_protrusions = list(np.unique(previous_mesh.segmentation))
        # [1:] because we ignore the base of zero:
        used_protrusions = used_protrusions[1:]
        p1_indices = previous_mesh.segmentation_unique[1:]
        p2_indices = self.segmentation_unique[1:]
        min_index = max(min_index, max(np.max(used_protrusions), np.max(p2_indices)))
        for ind in p2_indices:
            # If an index in mesh2 just happens to be in mesh1 already, we need to change it:
            if ind in used_protrusions:
                while True:
                    new_ind = randint(min_index, MAX_PROTRUSIONS_INDEX)
                    if new_ind not in used_protrusions:
                        self.segmentation[self.segmentation == ind] = new_ind
                        min_index = new_ind
                        break
            used_protrusions.append(ind)

        # Once all protrusion ID's are unique between meshes 1 and 2,
        # relabel the tracked protrusions in mesh 2:
        for protrusion_one_index in pairings:
            # Pairings is the order of the cell, we put it through p1_indices and p2_indices
            # to get u-shape3D coordinates:
            self.segmentation[
                self.segmentation == p2_indices[pairings[protrusion_one_index]]
            ] = p1_indices[protrusion_one_index]

            # We also want to update the index in the statistics as well (will make our job easier in the next section):
            self.statistics['index'][
                self.statistics['index'] == p2_indices[pairings[protrusion_one_index]]
                ] = p1_indices[protrusion_one_index]

        return min_index

    # Private method:
    def _load_segmentation(self, path_segmentation):
        # mat file is either new or old version:
        try:
            segment_dict = mat73.loadmat(path_segmentation)
        except:
            segment_dict = loadmat(path_segmentation)

        # Mat file contains either blebSegment variable or surfaceSegment variable:
        try:
            segmentation = segment_dict['blebSegment']
        except:
            segmentation = segment_dict['surfaceSegment']
            segmentation = np.squeeze(segmentation)
        return segmentation

    # Don't know how, but this should be STATIC METHOD:
    # (We will use it again later in the statistics step:)
    def load_statistics(self, path_statistics):
        # mat file is either new or old version:
        try:
            stats_dict = mat73.loadmat(path_statistics)
        except:
            stats_dict = loadmat(path_statistics)

        try:
            stats_dict = stats_dict['blebStats']
            # 3 surface area, 11 volume:
            converted_stats_dict = {'index': stats_dict[0][0][0][0][0],
                                    'volume': stats_dict[0][0][0][0][11],
                                    'surface_area': stats_dict[0][0][0][0][3]}
        except:
            # If we get an exception, it is because we are loading at the tracking step:
            converted_stats_dict = stats_dict

        return converted_stats_dict
