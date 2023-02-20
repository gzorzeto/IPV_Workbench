from pvlib import pvsystem, singlediode
import numpy as np
import multiprocess as mp
from tqdm import notebook
from ipv_workbench.translators import module_mapping as ipv_mm
from ipv_workbench.solver import calculations
from ipv_workbench.translators import panelizer
from ipv_workbench.utilities import circuits, utils, time_utils
import time
import copy
import pandas as pd


def main(panelizer_object, surface, string, tmy_location, dbt, psl, grid_pts, direct_ill, diffuse_ill):
    timeseries = panelizer_object.all_hoy
    ncpu = panelizer_object.ncpu
    modules = panelizer_object.get_modules(surface, string)
    module_dict_list = [panelizer_object.get_dict_instance([surface, string, module_name]) for module_name in modules]
    # pv_cells_xyz_arr_list = [np.array(panelizer_object.get_cells_xyz(surface, string, module_name)) for module_name in modules]
    # pv_cells_xyz_arr_chunks = []

    module_dict_chunks = np.array_split(module_dict_list, ncpu)
    module_name_chunks = np.array_split(modules, ncpu)
    pv_cells_xyz_arr_chunks = []
    for module_name_chunk in module_name_chunks:
        pv_cells_xyz_arr_chunks.append(
            [panelizer_object.get_cells_xyz(surface, string, module_name) for module_name in module_name_chunk])

    string_dict = panelizer_object.get_dict_instance([surface, string])
    string_details = string_dict['DETAILS']
    base_parameters = utils.get_cec_data(string_details['cec_key'], file_path=panelizer_object.cec_data)
    custom_module_data = pd.read_csv(panelizer_object.module_cell_data, index_col='scenario').loc[
        string_details['module_type']].to_dict()

    module_template = string_dict['DETAILS']['module_type']
    cell_type = ipv_mm.get_cell_type(module_template[0])
    orientation = ipv_mm.get_orientation(module_template[1])
    map_file = [fp for fp in panelizer_object.map_files if f"{cell_type}_{orientation}" in fp][0]
    default_submodule_map, default_diode_map, default_subcell_map = utils.read_map_excel(map_file)



    with mp.Pool(processes=ncpu) as pool:
        # print("    Pool Opened")

        args = list(zip(module_dict_chunks,
                        module_name_chunks,
                        [timeseries] * ncpu,
                        [tmy_location] * ncpu,
                        [dbt] * ncpu,
                        [psl] * ncpu,
                        pv_cells_xyz_arr_chunks,
                        [grid_pts] * ncpu,
                        [direct_ill] * ncpu,
                        [diffuse_ill] * ncpu,
                        [base_parameters] * ncpu,
                        [custom_module_data] * ncpu,
                        [default_submodule_map] * ncpu,
                        [default_diode_map] * ncpu,
                        [default_subcell_map] * ncpu,
                        [cell_type] * ncpu))
        # module_dict, surface, string, module, cell_area, cell_params, hoy_chunk

        mp_results = pool.starmap(panelizer.compile_system_multi_core, args)
        # print("    Result Gathered")
        # time.sleep(1)
        pool.close()
        # print("    Pool closed")
        pool.join()
        # print("    Pool joined")
    utils.unpack_mp_results(mp_results, panelizer_object, surface, string, modules, timeseries)



if __name__=="__main__":
    main(panelizer_object, surface, string, tmy_location, dbt, psl, grid_pts, direct_ill, diffuse_ill)