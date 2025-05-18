import os
import glob
import geopandas as gpd # Usaremos geopandas para leer GeoJSON fácilmente
from shapely.geometry import LineString # Para crear geometrías vacías si es necesario

def is_multiply_digitised(
    separator_type: str, 
    separator_width: float, 
    separator_length: float, 
    roadbed_distance: float,
    streets_nav_multidigit_value: str
) -> bool:
    """
    Determina si un segmento de carretera califica como Multiply Digitised según la especificación de HERE
    Y compara este estado calculado con el valor MULTIDIGIT proporcionado desde STREETS_NAV.
    
    Args:
        separator_type (str): Tipo de separador físico/visual (ej. 'physical_barrier', 'vegetation', 'rail', 'none', 'legal_barrier', 'elevated', 'tram', 'walkway').
        separator_width (float): Ancho del separador en metros.
        separator_length (float): Longitud de la separación en metros.
        roadbed_distance (float): Distancia entre las dos calzadas (líneas centrales), en metros.
        streets_nav_multidigit_value (str): El valor MULTIDIGIT de STREETS_NAV (ej. 'Y', 'N', None).
    
    Returns:
        bool: True si el estado calculado de Multiply Digitised coincide con streets_nav_multidigit_value.
              False en caso contrario (incluyendo si streets_nav_multidigit_value es inválido o None).
    """

    should_be_md = False

    # Condición 1: Anulación para preservar la consistencia visual (separador corto pero ancho)
    condition1_override = (separator_length < 100 and separator_width > 3)
    
    # Condición 2: Reglas generales para digitalización múltiple
    condition2_general = False
    if separator_type in ['physical_barrier', 'legal_barrier', 'rail', 'elevated', 'tram', 'walkway']:
        if separator_width > 3 and separator_length > 40 and roadbed_distance <= 80:
            condition2_general = True
    # Podría haber una condición adicional para 'vegetation' si las reglas de HERE lo especifican de forma diferente
    # elif separator_type == 'vegetation':
    #     if separator_width > X and separator_length > Y and roadbed_distance <= Z: # X, Y, Z según especificación
    #         condition2_general = True


    should_be_md = condition1_override or condition2_general
    
    calculated_md_char = 'Y' if should_be_md else 'N'

    if streets_nav_multidigit_value not in ['Y', 'N']:
        return False 

    return calculated_md_char == streets_nav_multidigit_value

def determine_dynamic_separator_type(nav_row, default_type='none') -> str:
    """
    Determina dinámicamente el tipo de separador basado en los atributos de STREETS_NAV.
    Los nombres de atributos y valores son supuestos y deben verificarse con la documentación.
    """
    form_of_way = nav_row.get('FORM_OF_WAY') 
    func_class = nav_row.get('FUNC_CLASS')   
    is_bridge = nav_row.get('BRIDGE_FG') == 'Y' or nav_row.get('BRIDGE') == 'Y' 
    is_tunnel = nav_row.get('TUNNEL_FG') == 'Y' or nav_row.get('TUNNEL') == 'Y'
    
    # Asumir que FOW puede ser numérico o string, adaptar según el PDF
    # Ejemplo de valores FOW (numéricos podrían ser de 0-30+):
    # 1, "Motorway", "Freeway", "Highway" -> physical_barrier
    # 2, "Multiple Carriageway", "Dual Carriageway", "Divided Highway" -> physical_barrier
    # 6, "Divided Road" (genérico) -> physical_barrier o vegetation
    # 4, "Roundabout" -> vegetation (para la isleta)
    # Otros como "Slip Road", "Service Road" usualmente no son MULTIDIGIT por separación.

    if is_bridge or is_tunnel:
        return 'physical_barrier'

    if form_of_way in [1, 2, '1', '2', 'Motorway', 'Multiple Carriageway', 'Dual Carriageway', 'Divided Highway', 'Freeway']:
        return 'physical_barrier'
    if form_of_way in [6, '6', 'Divided Road']: # Podría ser barrera o vegetación
        return 'physical_barrier' # O 'vegetation' si FC es menor
    if form_of_way in [4, '4', 'Roundabout']:
        return 'vegetation' 

    if func_class in [1, 2, '1', '2']:
        return 'physical_barrier'
    if func_class in [3, 4, '3', '4']:
        return 'vegetation' 
    if func_class in [5, '5']:
        return 'vegetation' 

    return default_type

def determine_dynamic_widths(nav_row, dynamic_separator_type, default_sep_width, default_rb_distance) -> tuple[float, float]:
    """
    Estima dinámicamente separator_width y roadbed_distance.
    Los valores son estimaciones y deben ajustarse según el PDF de HERE y los datos.
    """
    func_class = nav_row.get('FUNC_CLASS')
    # Convertir func_class a int si es string para comparaciones numéricas
    try:
        if isinstance(func_class, str):
            func_class = int(func_class)
    except (ValueError, TypeError):
        func_class = None # O un valor por defecto si no se puede convertir

    num_lanes_attr = nav_row.get('NUM_LANES', nav_row.get('LANE_COUNT_F', nav_row.get('LANE_COUNT_R'))) # Intentar varios nombres
    
    # Estimación del ancho de calzada por sentido
    typical_lane_width = 3.25  # Metros, un valor común
    estimated_lanes_per_direction = 1 # Valor por defecto muy conservador

    if num_lanes_attr is not None:
        try:
            estimated_lanes_per_direction = int(num_lanes_attr)
            if estimated_lanes_per_direction == 0: estimated_lanes_per_direction = 1 # Evitar 0 carriles
        except ValueError:
            estimated_lanes_per_direction = 1 
    elif func_class is not None:
        if func_class in [1, 2]:
            estimated_lanes_per_direction = 2
        elif func_class == 3:
            estimated_lanes_per_direction = 2
        elif func_class == 4:
            estimated_lanes_per_direction = 1
        else: # FC 5 o desconocido
            estimated_lanes_per_direction = 1
    
    estimated_roadway_half_width = estimated_lanes_per_direction * typical_lane_width

    # Estimaciones para separator_width y roadbed_distance
    est_separator_width = default_sep_width
    est_roadbed_distance = default_rb_distance

    if dynamic_separator_type == 'physical_barrier':
        if func_class in [1, 2]:
            est_separator_width = 3.0
        elif func_class == 3:
            est_separator_width = 2.0
        else: # FC 4, 5 o desconocido
            est_separator_width = 1.5
        est_roadbed_distance = (2 * estimated_roadway_half_width) + est_separator_width
    
    elif dynamic_separator_type == 'vegetation':
        if func_class in [1, 2, 3]:
            est_separator_width = 2.5
        elif func_class in [4, 5]:
            est_separator_width = 1.5
        else: # Desconocido
            est_separator_width = 2.0
        est_roadbed_distance = (2 * estimated_roadway_half_width) + est_separator_width

    elif dynamic_separator_type == 'legal_barrier':
        est_separator_width = 0.5 
        est_roadbed_distance = (2 * estimated_roadway_half_width) + est_separator_width
        
    elif dynamic_separator_type == 'elevated' or dynamic_separator_type == 'rail' or dynamic_separator_type == 'tram':
        # Estos son más difíciles de estimar sin datos específicos de la estructura
        est_separator_width = 4.0 # Suposición más amplia
        est_roadbed_distance = (2 * estimated_roadway_half_width) + est_separator_width

    elif dynamic_separator_type == 'walkway':
        est_separator_width = 1.5 # Ancho de una acera/camellón peatonal
        est_roadbed_distance = (2 * estimated_roadway_half_width) + est_separator_width

    elif dynamic_separator_type == 'none':
        est_separator_width = 0.1 # Casi nulo
        est_roadbed_distance = (2 * estimated_roadway_half_width) + est_separator_width
    
    # Asegurar que el ancho del separador no sea negativo si roadbed_distance es muy pequeño
    if est_roadbed_distance < (2 * estimated_roadway_half_width):
        est_roadbed_distance = (2 * estimated_roadway_half_width) + est_separator_width # Reajustar roadbed
    
    final_separator_width = est_roadbed_distance - (2 * estimated_roadway_half_width)
    if final_separator_width < 0:
        final_separator_width = 0 # No puede ser negativo

    return max(0.1, final_separator_width), max(0.1, est_roadbed_distance) # Evitar cero absoluto para evitar problemas


# --- Inicio de la lógica para procesar archivos ---
if __name__ == "__main__":
    streets_nav_directory = '/Users/josepablo13/Documents/José Pablo/Personal Projects/HERE Hackaton/data/STREETS_NAV/'
    geojson_nav_files = glob.glob(os.path.join(streets_nav_directory, "STREETS_NAV_*.geojson"))
    geojson_nav_files.extend(glob.glob(os.path.join(streets_nav_directory, "SREETS_NAV_*.geojson")))
    geojson_nav_files = list(set(geojson_nav_files)) 

    naming_addressing_directory = '/Users/josepablo13/Documents/José Pablo/Personal Projects/HERE Hackaton/data/STREETS_NAMING_ADDRESSING/'
    
    TARGET_CRS_METRIC = "EPSG:32614" 
    DEFAULT_LENGTH = 150.0 
    INITIAL_DEFAULT_SEPARATOR_TYPE = 'none' 
    # Valores por defecto iniciales para los anchos, serán sobrescritos por la estimación
    INITIAL_DEFAULT_WIDTH = 1.0 
    INITIAL_DEFAULT_ROADBED_DISTANCE = 7.0 # ej. 2 carriles de 3m + 1m separador

    print(f"Encontrados {len(geojson_nav_files)} archivos GeoJSON de STREETS_NAV en {streets_nav_directory}")

    for nav_filepath in geojson_nav_files:
        print(f"\nProcesando archivo STREETS_NAV: {os.path.basename(nav_filepath)}")
        
        tile_id = ""
        nav_basename = os.path.basename(nav_filepath)
        if nav_basename.startswith("STREETS_NAV_"):
            tile_id = nav_basename.replace("STREETS_NAV_", "").replace(".geojson", "")
        elif nav_basename.startswith("SREETS_NAV_"): 
            tile_id = nav_basename.replace("SREETS_NAV_", "").replace(".geojson", "")

        if not tile_id:
            print(f"  No se pudo extraer el tile_id de {nav_basename}. Saltando.")
            continue
        
        naming_filepath = os.path.join(naming_addressing_directory, f"SREETS_NAMING_ADDRESSING_{tile_id}.geojson")

        geometries_metric = {}
        if os.path.exists(naming_filepath):
            try:
                gdf_naming = gpd.read_file(naming_filepath)
                if not gdf_naming.empty and 'geometry' in gdf_naming.columns and 'link_id' in gdf_naming.columns:
                    gdf_naming_metric = gdf_naming.to_crs(TARGET_CRS_METRIC)
                    for _, naming_row in gdf_naming_metric.iterrows():
                        link_id_naming = naming_row.get('link_id')
                        geom = naming_row.geometry
                        if link_id_naming is not None and geom is not None and not geom.is_empty:
                            geometries_metric[link_id_naming] = geom
                    # print(f"  Cargadas y reproyectadas {len(geometries_metric)} geometrías de {os.path.basename(naming_filepath)}")
                # else:
                    # print(f"  Advertencia: El archivo {os.path.basename(naming_filepath)} está vacío o no tiene columnas 'geometry'/'link_id'.")
            except Exception as e:
                print(f"  Error cargando o reproyectando {os.path.basename(naming_filepath)}: {e}")
        # else:
            # print(f"  Advertencia: No se encontró el archivo STREETS_NAMING_ADDRESSING correspondiente: {os.path.basename(naming_filepath)}")

        try:
            gdf_nav = gpd.read_file(nav_filepath)
            
            if 'MULTIDIGIT' not in gdf_nav.columns:
                print(f"  Advertencia: La columna 'MULTIDIGIT' no existe en {os.path.basename(nav_filepath)}. Saltando este archivo.")
                continue

            required_cols_for_logic = ['FORM_OF_WAY', 'FUNC_CLASS'] # Añadir 'NUM_LANES' si se usa consistentemente
            missing_cols = [col for col in required_cols_for_logic if col not in gdf_nav.columns]
            if missing_cols:
                print(f"  Advertencia: Faltan columnas para la lógica dinámica en {os.path.basename(nav_filepath)}: {missing_cols}. Se usarán valores por defecto más genéricos.")

            processed_count = 0
            match_count = 0
            for index, nav_row in gdf_nav.iterrows():
                streets_nav_multidigit = nav_row.get('MULTIDIGIT')
                link_id_nav = nav_row.get('link_id', nav_row.get('LINK_ID'))

                dynamic_separator_length = DEFAULT_LENGTH
                if link_id_nav in geometries_metric:
                    try:
                        geom = geometries_metric[link_id_nav]
                        if geom and not geom.is_empty:
                            dynamic_separator_length = geom.length 
                    except Exception:
                        pass 
                
                dynamic_separator_type = INITIAL_DEFAULT_SEPARATOR_TYPE
                dynamic_separator_width = INITIAL_DEFAULT_WIDTH
                dynamic_roadbed_distance = INITIAL_DEFAULT_ROADBED_DISTANCE

                if not missing_cols:
                    dynamic_separator_type = determine_dynamic_separator_type(nav_row, default_type=INITIAL_DEFAULT_SEPARATOR_TYPE)
                    dynamic_separator_width, dynamic_roadbed_distance = determine_dynamic_widths(
                        nav_row, 
                        dynamic_separator_type, 
                        INITIAL_DEFAULT_WIDTH, 
                        INITIAL_DEFAULT_ROADBED_DISTANCE
                    )
                # Si faltan columnas, se usarán los INITIAL_DEFAULT para type, width, y roadbed_distance

                if streets_nav_multidigit not in ['Y', 'N']:
                    pass 

                coincide = is_multiply_digitised(
                    separator_type=dynamic_separator_type, 
                    separator_width=dynamic_separator_width,
                    separator_length=dynamic_separator_length, 
                    roadbed_distance=dynamic_roadbed_distance,
                    streets_nav_multidigit_value=str(streets_nav_multidigit) if streets_nav_multidigit is not None else ""
                )
                
                if coincide:
                    match_count += 1
                
                processed_count += 1
            
            print(f"  Total de segmentos procesados en {os.path.basename(nav_filepath)}: {processed_count}")
            print(f"  Coincidencias (con todos los params dinámicos/estimados): {match_count} de {processed_count}")

        except Exception as e:
            print(f"  Error procesando el archivo STREETS_NAV {os.path.basename(nav_filepath)}: {e}")

    print("\nProcesamiento completado.")